"""Local, structured question interpretation; this module never answers questions."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from threading import RLock

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / '.work/llm-benchmark/models/phi-3-mini-cpu-int4/cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4'
PACKAGES_PATH = ROOT / '.work/query-interpreter/packages'
EVALUATION_REPORT = ROOT / 'reports/assistant/local-query-interpreter-v1.json'
INTERPRETER_VERSION = 'phi3-query-interpreter-v1'
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
Question: Tell me about Ada Lovelace. JSON: {{"intent":"unsupported","slots":{{"author":"Ada Lovelace"}}}}
Citation counts/impact requests map to citation_unavailable. Affiliations map to institution_unavailable.
Methods, findings, abstracts, or paper summaries map to paper_content_unavailable because titles do not establish contents.
Use unsupported when no allowed DBLP request fits or intent is unclear. Never convert an unsupported request into a nearby supported one.
'''

_runtime = None
_runtime_lock = RLock()


def _get_runtime():
    global _runtime
    if _runtime is not None:
        return _runtime
    with _runtime_lock:
        if _runtime is not None:
            return _runtime
        try:
            report = json.loads(EVALUATION_REPORT.read_text(encoding='utf-8'))
            if (not str(report.get('status', '')).startswith('passed_candidate')
                    or report.get('passed_cases') != report.get('case_count')):
                return None
            if not MODEL_PATH.is_dir() or not PACKAGES_PATH.is_dir():
                return None
            sys.path.insert(0, str(PACKAGES_PATH))
            import onnxruntime_genai as og
            model = og.Model(str(MODEL_PATH))
            tokenizer = og.Tokenizer(model)
            _runtime = (og, model, tokenizer)
        except Exception:
            return None
    return _runtime


def _valid_plan(raw: str) -> dict | None:
    raw = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', raw, flags=re.I)
    start, end = raw.find('{'), raw.rfind('}')
    if start < 0 or end <= start:
        return None
    try:
        plan = json.loads(raw[start:end + 1])
    except (TypeError, ValueError):
        return None
    if (not isinstance(plan, dict) or set(plan) != {'intent', 'slots'}
            or plan.get('intent') not in INTENTS or not isinstance(plan.get('slots'), dict)
            or set(plan['slots']) - SLOTS):
        return None
    slots = {key: (None if value == '' else value) for key, value in plan['slots'].items()}
    for key, value in slots.items():
        if value is None:
            continue
        if key.startswith('year_'):
            if isinstance(value, bool) or not isinstance(value, int) or not 1900 <= value <= 2099:
                return None
        elif not isinstance(value, str) or not value.strip() or len(value) > 500:
            return None
        else:
            slots[key] = value.strip()
    required = {
        'author_publication_count': ('author',), 'author_latest_publication': ('author',),
        'author_lookup': ('author',), 'venue_publication_count': ('venue',),
        'venue_lookup': ('venue',), 'coauthor_pair': ('author_a', 'author_b'),
        'collaborator_ranking': ('author',), 'exact_title_lookup': ('title',),
        'paper_title_search': ('topic',),
    }
    if any(not slots.get(key) for key in required.get(plan['intent'], ())):
        return None
    year_from, year_to = slots.get('year_from'), slots.get('year_to')
    if year_from is not None and year_to is not None and year_from > year_to:
        return None
    # Irrelevant fields are discarded; only fields consumed by the selected fixed route survive.
    accepted = set(required.get(plan['intent'], ()))
    if plan['intent'] in {'author_publication_count', 'venue_publication_count',
                          'author_ranking', 'venue_ranking', 'publication_trend'}:
        accepted |= {'year_from', 'year_to'}
    return {'intent': plan['intent'], 'slots': {k: v for k, v in slots.items() if k in accepted}}


def interpret_question(question: str) -> dict | None:
    """Return a validated intent/slot plan, or None when inference is unavailable."""
    runtime = _get_runtime()
    if runtime is None:
        return None
    og, model, tokenizer = runtime
    with _runtime_lock:
        messages = [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': json.dumps({'question': question}, ensure_ascii=False)},
        ]
        prompt = tokenizer.apply_chat_template(json.dumps(messages, ensure_ascii=False), add_generation_prompt=True)
        input_tokens = tokenizer.encode(prompt)
        params = og.GeneratorParams(model)
        params.set_search_options(do_sample=False, temperature=0.0, top_k=1,
                                  max_length=len(input_tokens) + 80)
        generator = og.Generator(model, params)
        generator.append_tokens(input_tokens)
        try:
            while not generator.is_done():
                generator.generate_next_token()
            sequence = generator.get_sequence(0)
            raw = tokenizer.decode(sequence[len(input_tokens):]).strip()
        finally:
            del generator
    return _valid_plan(raw)


def generate_local_text(system: str, user: str, *, max_new_tokens: int = 240) -> str | None:
    """Run a bounded local completion with the already-approved assistant model."""
    runtime = _get_runtime()
    if runtime is None:
        return None
    og, model, tokenizer = runtime
    with _runtime_lock:
        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ]
        prompt = tokenizer.apply_chat_template(json.dumps(messages, ensure_ascii=False), add_generation_prompt=True)
        input_tokens = tokenizer.encode(prompt)
        params = og.GeneratorParams(model)
        params.set_search_options(do_sample=False, temperature=0.0, top_k=1,
                                  max_length=len(input_tokens) + max(1, min(400, max_new_tokens)))
        generator = og.Generator(model, params)
        generator.append_tokens(input_tokens)
        try:
            while not generator.is_done():
                generator.generate_next_token()
            sequence = generator.get_sequence(0)
            return tokenizer.decode(sequence[len(input_tokens):]).strip()
        finally:
            del generator


def close_interpreter() -> None:
    global _runtime
    with _runtime_lock:
        if _runtime is not None:
            _runtime = None
            import gc
            gc.collect()
