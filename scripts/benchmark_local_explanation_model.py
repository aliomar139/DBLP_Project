"""Evaluate a local model only as a wording layer over bounded evidence packets."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import re
import sys
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
sys.path.insert(0, str(ROOT / '.work/rag-benchmark/packages'))
sys.path.insert(0, str(ROOT / '.work/llm-benchmark/packages'))

import onnxruntime_genai as og
import psutil

from backend.app.services import assistant_tools

MODEL_PATH = ROOT / '.work/llm-benchmark/models/phi-3-mini-cpu-int4/cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4'
MODEL_SETUP_REPORT = ROOT / 'reports/assistant/local-model-phi3-int4-setup-v1.json'
OUTPUT = ROOT / 'reports/assistant/local-explanation-benchmark-v1.json'
SYSTEM = (
    'You are a wording layer for a DBLP research assistant. Use only the supplied '
    'evidence packet. Do not use outside knowledge or guess. Every factual answer '
    'must cite evidence references from the packet. If a field is explicitly marked '
    'unavailable, return unavailable. If the evidence is too weak for the requested '
    'claim, return insufficient_evidence with a short explanation. '
    'For an answerable entity count, include the entity name and exact count in a complete sentence. '
    'For unavailable facts, give a nonempty sentence that clearly states the fact is unavailable. '
    'Use the exact status required in the response contract. Do not infer gender or use gendered pronouns; refer to people by their supplied names. '
    'Return exactly one JSON object with keys status, answer, evidence_refs. Do not '
    'include markdown or any other keys.'
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def make_cases() -> list[dict]:
    corpus = assistant_tools.corpus_count()
    corpus_packet = {
        'query': 'How many publication records are stored in this DBLP dataset?',
        'evidence': [{'ref': 'calculation:corpus_count', 'kind': corpus.kind,
                      'calculation': corpus.calculation, 'value': corpus.row,
                      'filters': corpus.filters}],
        'expected_status': 'answered', 'required_numbers': [str(corpus.row['publication_count'])],
        'required_phrases': ['DBLP'],
        'required_refs': ['calculation:corpus_count'],
    }

    # Resolve the test subject from active DBLP data, then collect count evidence
    # with the approved bounded tools before constructing any model input.
    from backend.app.database import get_connection
    from contextlib import closing
    with closing(get_connection()) as db:
        name, author_id = db.execute(
            'SELECT a.name, a.author_id FROM authors a JOIN publication_authors pa '
            'ON pa.author_id=a.author_id WHERE a.name IS NOT NULL '
            'ORDER BY a.author_id LIMIT 1').fetchone()
    author = assistant_tools.resolve_entity('author', str(name))
    if len(author) != 1:
        raise RuntimeError('The local benchmark author did not resolve to one record')
    count = assistant_tools.publication_count('author', int(author_id))
    author_packet = {
        'query': f'How many publications are assigned to {name}?',
        'evidence': [
            {'ref': f'author:{author_id}', 'kind': 'author', 'value': author[0].row},
            {'ref': f'calculation:author_count:{author_id}', 'kind': count.kind,
             'calculation': count.calculation, 'value': count.row, 'filters': count.filters},
        ],
        'expected_status': 'answered',
        'required_numbers': [str(count.row['publication_count'])],
        'required_phrases': [str(name)],
        'required_refs': [f'author:{author_id}', f'calculation:author_count:{author_id}'],
    }
    limitation_cases = [
        {'case_id': 'citation_unavailable',
         'question': 'How many observed citations does the author have?',
         'evidence': {'available': False, 'reason': 'Observed citation counts are not approved DBLP evidence.'},
         'expected_status': 'unavailable', 'required_phrases': ['unavailable']},
        {'case_id': 'paper_methods_unavailable',
         'question': 'What method did the paper use?',
         'evidence': {'available': False, 'reason': 'Only a paper title is available; titles do not establish methods.'},
         'expected_status': 'insufficient_evidence',
         'required_phrases': ['not specified in the available evidence']},
    ]
    cases = [
        {'case_id': 'corpus_count', **corpus_packet},
        {'case_id': 'author_publication_count', **author_packet},
    ]
    cases.extend({
        'case_id': item['case_id'],
        'query': item['question'],
        'evidence': [item['evidence']],
        'expected_status': item['expected_status'],
        'required_numbers': [], 'required_phrases': item['required_phrases'], 'required_refs': [],
    } for item in limitation_cases)
    return cases


def generate(model, tokenizer, case: dict, max_new_tokens: int) -> tuple[str, int, float]:
    messages = [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': json.dumps({
            'query': case['query'], 'evidence': case['evidence'],
            'answer_requirements': {
                'exact_status_required': case['expected_status'],
                'required_phrases': case.get('required_phrases', []),
                'required_numeric_values': case.get('required_numbers', []),
                'required_evidence_references': case.get('required_refs', []),
                'answer_must_be_nonempty': True,
            },
            'required_response_shape': {
                'status': ['answered', 'insufficient_evidence'],
                'answer': 'string', 'evidence_refs': 'array of supplied ref strings'},
        }, ensure_ascii=False)},
    ]
    prompt = tokenizer.apply_chat_template(json.dumps(messages, ensure_ascii=False),
                                           add_generation_prompt=True)
    input_tokens = tokenizer.encode(prompt)
    params = og.GeneratorParams(model)
    params.set_search_options(do_sample=False, temperature=0.0, top_k=1,
                              max_length=len(input_tokens) + max_new_tokens)
    generator = og.Generator(model, params)
    generator.append_tokens(input_tokens)
    started = perf_counter()
    while not generator.is_done():
        generator.generate_next_token()
    elapsed = perf_counter() - started
    sequence = generator.get_sequence(0)
    output_tokens = max(0, len(sequence) - len(input_tokens))
    output = tokenizer.decode(sequence[len(input_tokens):]).strip()
    del generator
    gc.collect()
    return output, output_tokens, elapsed


def validate(case: dict, raw: str) -> dict:
    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        return {'json_valid': False, 'status_valid': False, 'refs_valid': False,
                'numbers_supported': False, 'required_content_present': False,
                'answer_claims_accepted': False}
    answer = result.get('answer') if isinstance(result, dict) else None
    nonempty_answer = isinstance(answer, str) and len(answer.strip()) >= 12
    refs = result.get('evidence_refs') if isinstance(result, dict) else None
    status_valid = isinstance(result, dict) and result.get('status') == case['expected_status']
    known_refs = {str(e['ref']) for e in case['evidence'] if isinstance(e, dict) and 'ref' in e}
    refs_valid = isinstance(refs, list) and all(isinstance(ref, str) and ref in known_refs for ref in refs)
    if case['expected_status'] == 'answered':
        refs_valid = refs_valid and set(case['required_refs']) <= set(refs or [])
    evidence_text = json.dumps(case['evidence'], ensure_ascii=False)
    number_tokens = re.findall(r'(?<![\w])\d[\d,]*(?:\.\d+)?', str(answer))
    numbers_supported = all(token.replace(',', '') in evidence_text.replace(',', '') for token in number_tokens)
    numeric_answer = {token.replace(',', '') for token in number_tokens}
    required_numbers_present = all(str(value).replace(',', '') in numeric_answer
                                   for value in case.get('required_numbers', []))
    required_phrases_present = all(value.lower() in str(answer).lower()
                                   for value in case.get('required_phrases', []))
    required_content = required_numbers_present and required_phrases_present
    has_link = bool(re.search(r'https?://|/(?:authors|venues|papers|topics)/\d+', str(answer)))
    gendered_pronoun = bool(re.search(r'\b(?:he|she|him|her|his|hers)\b', str(answer), re.I))
    no_extra_fields = isinstance(result, dict) and set(result) == {'status', 'answer', 'evidence_refs'}
    return {
        'json_valid': True,
        'status_valid': bool(status_valid),
        'refs_valid': bool(refs_valid),
        'numbers_supported': bool(numbers_supported),
        'required_content_present': bool(required_content),
        'nonempty_answer': bool(nonempty_answer),
        'no_generated_links': not has_link,
        'no_inferred_gender': not gendered_pronoun,
        'no_extra_fields': bool(no_extra_fields),
        'answer_claims_accepted': bool(status_valid and refs_valid and numbers_supported and
                                       required_content and nonempty_answer and not has_link and
                                       not gendered_pronoun and no_extra_fields),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-new-tokens', type=int, default=128)
    parser.add_argument('--show-candidate-text', action='store_true',
                        help='Print generated text for manual evaluation; never writes it to the report.')
    args = parser.parse_args()
    setup = json.loads(MODEL_SETUP_REPORT.read_text(encoding='utf-8'))
    if setup.get('status') != 'downloaded_for_local_benchmark_only':
        raise RuntimeError('The model snapshot has not completed its pinned setup')
    cases = make_cases()
    load_started = perf_counter()
    model = og.Model(str(MODEL_PATH))
    tokenizer = og.Tokenizer(model)
    load_seconds = perf_counter() - load_started
    process = psutil.Process()
    peak_bytes = getattr(process.memory_info(), 'peak_wset', process.memory_info().rss)
    results = []
    for case in cases:
        raw, output_tokens, seconds = generate(model, tokenizer, case, args.max_new_tokens)
        validation = validate(case, raw)
        if args.show_candidate_text:
            print(json.dumps({'case_id': case['case_id'], 'candidate_text': raw}, ensure_ascii=False))
        peak_bytes = max(peak_bytes, getattr(process.memory_info(), 'peak_wset', process.memory_info().rss))
        results.append({'case_id': case['case_id'], 'latency_seconds': seconds,
                        'output_tokens': output_tokens, **validation})
    latencies = [item['latency_seconds'] for item in results]
    ordered = sorted(latencies)
    p95 = ordered[max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999) - 1))]
    passed = all(item['answer_claims_accepted'] for item in results)
    report = {
        'version': 1,
        'status': 'benchmark_passed_candidate_not_selected' if passed else 'benchmark_failed_candidate_not_selected',
        'model': setup['repository'], 'revision': setup['revision'],
        'onnxruntime_genai_version': '0.16.0', 'execution_provider': 'CPU',
        'evidence_source': 'active DuckDB through bounded assistant tools; the model receives serialized packets only',
        'inference_calls_local_only': True, 'question_text_written_to_report': False,
        'model_load_seconds': load_seconds,
        'peak_process_working_set_bytes': peak_bytes,
        'case_count': len(results), 'answer_claims_accepted_count': sum(r['answer_claims_accepted'] for r in results),
        'unsupported_claims_observed': sum(not r['answer_claims_accepted'] for r in results),
        'latency_seconds': {'mean': mean(latencies), 'p95_nearest_rank': p95,
                            'max': max(latencies)},
        'cases': results,
        'qualification': 'Small local development grounding probe; passing does not prove future outputs cannot hallucinate. The model is not integrated into API responses by this benchmark.',
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    del model, tokenizer
    gc.collect()


if __name__ == '__main__':
    main()
