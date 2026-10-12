"""The same missing-core question cannot regress into a tangential answer."""

import json
from decimal import Decimal, InvalidOperation
from unittest.mock import AsyncMock

import pytest

from services.answer_contract import requested_parts
from services.grounded_answers import (
    answer,
    checked_calculations,
    gap,
    helpful_result,
    number_tokens,
    operand,
)

QUESTION = ("We are a state-licensed microfinance bank in Lagos with ₦1.2bn in paid-up capital. "
            "Which current CBN capital requirements apply to us, what is our gap, and what are the deadlines?")
NEWS = "Inability to maintain minimum capital unimpaired by losses was a reason for licence revocation."


@pytest.mark.parametrize('reported_gaps', [[], ['current_applicability'], ['other_requested_fact']])
@pytest.mark.asyncio
async def test_three_runs_with_different_model_gaps_have_the_same_missing_core_opening(reported_gaps):
    draft = dict(answerable=not reported_gaps,
        claims=[dict(text=NEWS, chunk_id='news-1', quote=NEWS, additional_evidence=[])],
        calculations=[], missing_information=reported_gaps, direct_answer='',
        followup_questions=['What other breaches caused licence revocation?'])
    audit = dict(answerable=True, supported_claims=[True], supported_calculations=[],
        issues=[], missing_information=[], direct_answer_supported=True,
        irrelevant_draft_gaps=reported_gaps, answered_parts=['capital_requirement', 'capital_gap', 'deadline'])
    result = await answer(QUESTION, {'sources': [dict(chunk_id='news-1', document_id='news',
        title='Synthetic news recap', content=NEWS, provenance={})]},
        AsyncMock(side_effect=[json.dumps(draft), json.dumps(audit)]), answer_mode='helpful')
    assert result['answer'].startswith('I cannot establish the applicable capital minimum, your actual capital gap and the applicable deadlines')
    assert set(requested_parts(QUESTION)) <= set(result['missing_information'])
    assert result['answer_status'] == 'partial'
    assert NEWS in result['answer']  # Honest useful finding retained, below the opening.
    assert 'latest audited capital unimpaired by losses' in result['suggested_followups'][0]
    assert not any('revocation' in followup for followup in result['suggested_followups'])
    for heading in ('What is established', 'What is not established', 'Needed from you', 'Next step'):
        assert result['answer'].count('**' + heading + '**') == 1
    again = helpful_result(result, QUESTION)
    assert again['answer'].count('**Next step**') == 1


@pytest.mark.parametrize('text,expected', [
    ('₦1.2bn', '1200000000'), ('N1.2bn', '1200000000'), ('NGN 1.2 billion', '1200000000'),
    ('₦500 million', '500000000'), ('200m', '200000000'), ('* 12', '12'),
    ('1,000.50', '1000.50'), ('10%', '0.1'), ('-2.5mn', '-2500000'),
])
def test_exact_unit_normalization(text, expected):
    assert operand(text) == Decimal(expected)


@pytest.mark.parametrize('text', ['1.2 bananas', '1.2bn USD extra', '1/2', '1,00', 'NaN'])
def test_unknown_or_ambiguous_units_never_get_silently_stripped(text):
    with pytest.raises(InvalidOperation):
        operand(text)


def test_scale_is_part_of_number_evidence():
    assert number_tokens('₦1.2bn') == {'1200000000'}
    assert '1.2' not in number_tokens('N1.2bn')
    assert number_tokens('₦500m') == number_tokens('NGN 500,000,000')
    assert number_tokens('2026-09-27') == {'2026', '9', '27'}


def test_bn_gap_calculation_is_recomputed_in_base_units():
    quote = 'The synthetic capital minimum is ₦1 billion.'
    sources = {'rule': dict(chunk_id='rule', document_id='rule', content=quote)}
    calculations, results = checked_calculations({'calculations': [dict(
        left='₦1bn', right='₦1.2bn', operation='subtract', chunk_id='rule', quote=quote)]}, sources, QUESTION)
    assert len(calculations) == 1
    assert results == {'-200000000'}
    assert '999999998.8' not in calculations[0]['result']


def test_explicit_cross_currency_subtraction_is_rejected():
    quote = 'The balance is USD 500 million.'
    calculations, _ = checked_calculations({'calculations': [dict(
        left='USD 500m', right='NGN 500m', operation='subtract', chunk_id='rule', quote=quote)]},
        {'rule': dict(chunk_id='rule', document_id='rule', content=quote)}, 'Compare NGN 500m.')
    assert calculations == []


def test_a_percentage_operand_is_not_multiplied_as_a_whole_number():
    quote = 'The synthetic fee is 10% of the base amount of 1000.'
    calculations, results = checked_calculations({'calculations': [dict(
        left='1000', right='10%', operation='multiply', chunk_id='rule', quote=quote)]},
        {'rule': dict(chunk_id='rule', document_id='rule', content=quote)}, 'Calculate the fee.')
    assert len(calculations) == 1 and results == {'100'}


def test_no_sources_still_names_the_unanswered_core_parts_first():
    result = helpful_result(gap('retrieval_unavailable'), QUESTION)
    assert result['answer'].startswith('I cannot establish the applicable capital minimum')
    assert set(requested_parts(QUESTION)) <= set(result['missing_information'])
    assert 'shortfall = max(0,' in result['answer']
    assert result['suggested_actions'][0] == 'Retry the question when document search is available.'


def test_historical_findings_cannot_be_mislabelled_as_current_answer_coverage():
    result = helpful_result(dict(answer='A historical source states a minimum and an old deadline.',
        knowledge_gap=False, missing_information=['current_applicability']), QUESTION)
    assert result['answer'].startswith('I cannot establish the applicable capital minimum and the applicable deadlines')
    assert {'capital_requirement', 'deadline'} <= set(result['missing_information'])
