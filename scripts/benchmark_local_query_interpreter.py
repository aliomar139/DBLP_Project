"""Evaluate local Phi-3 as a constrained DBLP question interpreter."""
from __future__ import annotations

import argparse
import ctypes
import gc
import json
import re
import sys
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.work/query-interpreter/packages'))
import onnxruntime_genai as og

MODEL_PATH = ROOT / '.work/llm-benchmark/models/phi-3-mini-cpu-int4/cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4'
SETUP_REPORT = ROOT / 'reports/assistant/local-model-phi3-int4-setup-v1.json'
OUTPUT = ROOT / 'reports/assistant/local-query-interpreter-v1.json'
INTENTS = {
    'author_publication_count', 'author_latest_publication', 'author_lookup',
    'venue_publication_count', 'venue_lookup', 'corpus_publication_count',
    'author_ranking', 'venue_ranking', 'publication_trend', 'coauthor_pair',
    'collaborator_ranking', 'exact_title_lookup', 'paper_title_search',
    'citation_unavailable', 'institution_unavailable', 'paper_content_unavailable',
    'unsupported',
}
SLOTS = {'author', 'venue', 'author_a', 'author_b', 'title', 'topic', 'year_from', 'year_to'}
SYSTEM = f'''Classify the user's request for a DBLP bibliographic assistant. Output one JSON object only: intent and slots.
Choose one exact intent from this list: {', '.join(sorted(INTENTS))}.
slots may contain any of these exact keys: {', '.join(sorted(SLOTS))}. Include only non-null values.
Name/title/topic values are strings. Years are integers. Copy only details stated by the user.
Do not answer. Do not add facts, gender, pronouns, commentary, SQL, markdown, or extra keys.
Examples:
Question: How many papers did Ada Lovelace publish? JSON: {{"intent":"author_publication_count","slots":{{"author":"Ada Lovelace"}}}}
Question: How many DBLP papers are there in total? JSON: {{"intent":"corpus_publication_count","slots":{{}}}}
Question: What did the newest Ada Lovelace paper use? JSON: {{"intent":"paper_content_unavailable","slots":{{"author":"Ada Lovelace"}}}}
Question: Which Ada Lovelace paper has the most citations? JSON: {{"intent":"citation_unavailable","slots":{{"author":"Ada Lovelace"}}}}
Question: Tell me about Ada Lovelace. JSON: {{"intent":"unsupported","slots":{{"author":"Ada Lovelace"}}}}
Question: How many DBLP papers appeared each year from 2019 to 2023? JSON: {{"intent":"publication_trend","slots":{{"year_from":2019,"year_to":2023}}}}
Question: Who publishes most often with Ada Lovelace? JSON: {{"intent":"collaborator_ranking","slots":{{"author":"Ada Lovelace"}}}}
Question: Ada Lovelace. JSON: {{"intent":"unsupported","slots":{{"author":"Ada Lovelace"}}}}
Citation counts/impact requests map to citation_unavailable. Affiliations map to institution_unavailable.
Methods, findings, abstracts, or paper summaries map to paper_content_unavailable because titles do not establish contents.
Use unsupported when no allowed DBLP request fits or intent is unclear. Never convert an unsupported request into a nearby supported one.
'''

# Expected intent and non-null slots are reviewed examples; question text is intentionally
# fixed and contains no private user queries.
CASES = [
    ('author_count_howmany', 'How many papers has Ada Lovelace written?', 'author_publication_count', {'author': 'Ada Lovelace'}),
    ('author_count_colloquial', 'Give me Ada Lovelace’s publication total.', 'author_publication_count', {'author': 'Ada Lovelace'}),
    ('author_count_indirect', 'I’m trying to find out how much research Ada Lovelace published between 2018 and 2022.', 'author_publication_count', {'author': 'Ada Lovelace', 'year_from': 2018, 'year_to': 2022}),
    ('author_latest', 'What’s the newest paper listed for Ada Lovelace?', 'author_latest_publication', {'author': 'Ada Lovelace'}),
    ('author_lookup', 'Can you pull up the DBLP profile for Ada Lovelace?', 'author_lookup', {'author': 'Ada Lovelace'}),
    ('venue_count', 'How many papers appeared in Example Journal?', 'venue_publication_count', {'venue': 'Example Journal'}),
    ('venue_lookup', 'Show me the venue Example Journal.', 'venue_lookup', {'venue': 'Example Journal'}),
    ('corpus_count', 'How large is the DBLP collection in publication records?', 'corpus_publication_count', {}),
    ('author_ranking', 'Which researchers have the biggest publication totals?', 'author_ranking', {}),
    ('venue_ranking', 'Where are the most papers published?', 'venue_ranking', {}),
    ('publication_trend', 'Show the number of DBLP papers per year from 2019 through 2023.', 'publication_trend', {'year_from': 2019, 'year_to': 2023}),
    ('coauthor_pair', 'Did Ada Lovelace and Alan Turing ever publish together?', 'coauthor_pair', {'author_a': 'Ada Lovelace', 'author_b': 'Alan Turing'}),
    ('collaborators', 'Who publishes most often with Ada Lovelace?', 'collaborator_ranking', {'author': 'Ada Lovelace'}),
    ('exact_title', 'Find the paper called "A Sample Paper".', 'exact_title_lookup', {'title': 'A Sample Paper'}),
    ('title_search', 'I need papers related to database query optimization.', 'paper_title_search', {'topic': 'database query optimization'}),
    ('citation_refusal', 'Which paper by Ada Lovelace has the most citations?', 'citation_unavailable', {'author': 'Ada Lovelace'}),
    ('institution_refusal', 'Where does Ada Lovelace work?', 'institution_unavailable', {'author': 'Ada Lovelace'}),
    ('paper_methods_refusal', 'What method did the paper "A Sample Paper" use?', 'paper_content_unavailable', {'title': 'A Sample Paper'}),
    ('unsupported_weather', 'Will it rain tomorrow?', 'unsupported', {}),
    ('unsupported_ambiguous', 'Tell me about Ada Lovelace.', 'unsupported', {}),
]


class _MemoryCounters(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]


def peak_working_set() -> int:
    counters = _MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel32.GetCurrentProcess()
    getter = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    getter.argtypes = (ctypes.c_void_p, ctypes.POINTER(_MemoryCounters), ctypes.c_ulong)
    getter.restype = ctypes.c_int
    if not getter(process, ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.PeakWorkingSetSize)


def generate(model, tokenizer, question: str, limit: int) -> tuple[str, float, int]:
    messages = [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': json.dumps({'question': question}, ensure_ascii=False)},
    ]
    prompt = tokenizer.apply_chat_template(json.dumps(messages, ensure_ascii=False), add_generation_prompt=True)
    tokens = tokenizer.encode(prompt)
    params = og.GeneratorParams(model)
    params.set_search_options(do_sample=False, temperature=0.0, top_k=1,
                              max_length=len(tokens) + limit)
    generator = og.Generator(model, params)
    generator.append_tokens(tokens)
    started = perf_counter()
    while not generator.is_done():
        generator.generate_next_token()
    elapsed = perf_counter() - started
    sequence = generator.get_sequence(0)
    count = max(0, len(sequence) - len(tokens))
    output = tokenizer.decode(sequence[len(tokens):]).strip()
    del generator
    gc.collect()
    return output, elapsed, count


def validate(raw: str, expected_intent: str, expected_slots: dict) -> dict:
    raw = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', raw, flags=re.I)
    start, end = raw.find('{'), raw.rfind('}')
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {'json_valid': False, 'schema_valid': False, 'intent_correct': False,
                'slots_correct': False, 'pass': False}
    schema = (isinstance(parsed, dict) and set(parsed) == {'intent', 'slots'}
              and parsed.get('intent') in INTENTS and isinstance(parsed.get('slots'), dict)
              and set(parsed.get('slots', {})) <= SLOTS)
    if not schema:
        return {'json_valid': True, 'schema_valid': False, 'intent_correct': False,
                'slots_correct': False, 'pass': False}
    intent_ok = parsed['intent'] == expected_intent
    expected = {slot: expected_slots.get(slot) for slot in SLOTS}
    actual = {slot: (None if parsed['slots'].get(slot) == '' else parsed['slots'].get(slot))
              for slot in SLOTS}
    slots_ok = actual == expected
    # An explicit gender/pronoun term in values is always a failure; there is no
    # user-facing text in this protocol, so the model has nowhere to express gender.
    values = json.dumps(parsed, ensure_ascii=False)
    neutral = not re.search(r'\b(?:he|she|him|her|his|hers)\b', values, re.I)
    return {'json_valid': True, 'schema_valid': True, 'intent_correct': intent_ok,
            'slots_correct': slots_ok, 'neutral_output': neutral,
            'pass': bool(intent_ok and slots_ok and neutral)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-new-tokens', type=int, default=100)
    parser.add_argument('--show-output', action='store_true', help='Print model output for manual review.')
    parser.add_argument('--case-id', action='append', help='Run only a named case; may be repeated.')
    args = parser.parse_args()
    setup = json.loads(SETUP_REPORT.read_text(encoding='utf-8'))
    if setup.get('status') != 'downloaded_for_local_benchmark_only':
        raise RuntimeError('The pinned model setup report is missing or not complete')
    started = perf_counter()
    model = og.Model(str(MODEL_PATH))
    tokenizer = og.Tokenizer(model)
    load_seconds = perf_counter() - started
    peak = peak_working_set()
    results = []
    cases = [case for case in CASES if not args.case_id or case[0] in args.case_id]
    for case_id, question, intent, slots in cases:
        raw, seconds, token_count = generate(model, tokenizer, question, args.max_new_tokens)
        checks = validate(raw, intent, slots)
        if args.show_output:
            print(json.dumps({'case_id': case_id, 'output': raw}, ensure_ascii=False))
        peak = max(peak, peak_working_set())
        results.append({'case_id': case_id, 'seconds': seconds, 'output_tokens': token_count, **checks})
    times = sorted(row['seconds'] for row in results)
    p95 = times[max(0, min(len(times) - 1, int(.95 * len(times) + .999) - 1))]
    passed = all(row['pass'] for row in results)
    report = {
        'version': 1,
        'status': 'passed_candidate_not_connected' if passed else 'failed_candidate_not_connected',
        'model': setup['repository'], 'revision': setup['revision'],
        'evaluation_role': 'structured question intent and slot extraction only; no generated answers',
        'inference_local_only': True, 'question_text_written_to_report': False,
        'case_count': len(results), 'case_ids': [row['case_id'] for row in results],
        'passed_cases': sum(row['pass'] for row in results),
        'model_load_seconds': load_seconds, 'latency_seconds': {'mean': mean(times), 'p95_nearest_rank': p95, 'max': max(times)},
        'peak_process_working_set_bytes': peak, 'cases': results,
        'qualification': ('20 fixed reviewed development examples; passing does not prove robust handling of arbitrary phrasing. Route remains unconnected pending review.'
                          if not args.case_id else 'Targeted follow-up subset only; not a full evaluation. Route remains unconnected pending review.'),
    }
    output_path = OUTPUT if not args.case_id else ROOT / '.work/query-interpreter/targeted-review.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    del model, tokenizer
    gc.collect()


if __name__ == '__main__':
    main()
