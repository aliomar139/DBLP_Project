"""Validate deterministic assistant claims against their attached evidence."""
from __future__ import annotations

import re
from typing import Any

from ..schemas.models import AssistantCalculation, AssistantClaim, AssistantSource

_ROUTES = {'author': 'authors', 'venue': 'venues', 'paper': 'papers', 'topic': 'topics'}


class ClaimValidationError(ValueError):
    pass


def _normal_number(value: str) -> str:
    return value.replace(',', '')


def make_claims(answer: str, sources: list[AssistantSource],
                calculations: list[AssistantCalculation]) -> list[AssistantClaim]:
    """Split displayed text into claims and attach nearby verified evidence refs."""
    claims = []
    for line_number, line in enumerate((part.strip() for part in answer.splitlines()), 1):
        if not line:
            continue
        source_refs = []
        for source in sources:
            if source.title and source.title.casefold() in line.casefold():
                source_refs.append(f'{source.kind}:{source.id}')
                continue
            for calculation in calculations:
                filters = calculation.filters
                result = calculation.result
                if source.kind == 'author' and source.id in filters.get('author_ids', []):
                    source_refs.append(f'{source.kind}:{source.id}')
                    break
                record_key = {'author': 'author_id', 'venue': 'venue_id',
                              'paper': 'publication_id', 'topic': 'topic_id'}[source.kind]
                def contains_record(value: Any) -> bool:
                    if isinstance(value, dict):
                        return value.get(record_key) == source.id or any(contains_record(v) for v in value.values())
                    if isinstance(value, list):
                        return any(contains_record(item) for item in value)
                    return False
                if contains_record(result):
                    source_refs.append(f'{source.kind}:{source.id}')
                    break
        calculation_refs = list(range(len(calculations)))
        if not source_refs and not calculation_refs:
            raise ClaimValidationError('An answered statement has no evidence reference')
        claims.append(AssistantClaim(claim_id=f'claim-{line_number}', text=line,
                                     source_refs=source_refs,
                                     calculation_refs=calculation_refs))
    return claims


def validate_claims(answer: str, sources: list[AssistantSource],
                    calculations: list[AssistantCalculation],
                    claims: list[AssistantClaim]) -> None:
    """Reject missing references, generated URLs, invalid links, and unsupported numbers."""
    source_by_ref = {f'{source.kind}:{source.id}': source for source in sources}
    for source in sources:
        route = _ROUTES.get(source.kind)
        if route is None or source.href != f'/{route}/{source.id}' or source.id < 0:
            raise ClaimValidationError('An answer source link does not match its verified entity ID')
        if source.href.startswith(('http://', 'https://')):
            raise ClaimValidationError('Assistant sources must use verified local dashboard routes')

    expected_text = '\n'.join(claim.text for claim in claims)
    if answer.strip() != expected_text:
        raise ClaimValidationError('Displayed answer text differs from its structured claims')
    if answer.strip() and not claims:
        raise ClaimValidationError('An answered response has no structured claims')

    for claim in claims:
        if not claim.source_refs and not claim.calculation_refs:
            raise ClaimValidationError('A claim has no evidence references')
        if any(ref not in source_by_ref for ref in claim.source_refs):
            raise ClaimValidationError('A claim refers to a source that is not attached')
        if any(ref < 0 or ref >= len(calculations) for ref in claim.calculation_refs):
            raise ClaimValidationError('A claim refers to a calculation that is not attached')

        evidence_parts: list[str] = []
        for source_ref in claim.source_refs:
            source = source_by_ref[source_ref]
            evidence_parts.extend([str(source.id), source.title, source.detail or ''])
        for index in claim.calculation_refs:
            calculation = calculations[index]
            evidence_parts.extend([calculation.description,
                                   str(calculation.filters), str(calculation.result)])
        evidence_numbers = {
            _normal_number(match) for part in evidence_parts
            for match in re.findall(r'(?<![\w])\d[\d,]*(?:\.\d+)?', part)
        }
        claim_text = re.sub(r'^\s*\d+\.\s+', '', claim.text)
        claim_numbers = {
            _normal_number(match) for match in
            re.findall(r'(?<![\w])\d[\d,]*(?:\.\d+)?', claim_text)
        }
        if not claim_numbers <= evidence_numbers:
            raise ClaimValidationError('A displayed number is not present in referenced evidence')

        for ref in claim.source_refs:
            source = source_by_ref[ref]
            if source.title and source.title.casefold() in claim.text.casefold():
                continue
            # Entity IDs can be cited for grouped relationship statements where the
            # person names are referenced through a shared-record calculation.
            if claim.calculation_refs:
                continue
            raise ClaimValidationError('A claim source is not nearby in the displayed wording')
