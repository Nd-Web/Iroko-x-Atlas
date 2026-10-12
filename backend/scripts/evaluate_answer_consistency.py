"""Repeat real, read-only chat answers without saving chats or running ingestion.

Run from backend after configuring .env. Case files are evaluation data, not prompts
or application defaults. Reports may contain questions/answers; keep them private.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def evaluate(args):
    from agents.strategist import StrategistAgent
    from ingestion.access import as_user
    from ingestion.db import Session
    from models.database import User

    cases = json.loads(Path(args.cases).read_text(encoding='utf-8'))
    results = []
    with Session() as db:
        user = db.get(User, args.user_id)
        if user is None or not user.is_active:
            raise ValueError('An existing active user is required; this tool never creates access')
        with as_user(user):
            for case in cases:
                for run in range(args.repeats):
                    agent = StrategistAgent()
                    # Read-only evidence orchestration, no saved chat/alert/trace writes.
                    try:
                        result = await agent._orchestrate_agents(case['question'], False, 'standard')
                        text = result.get('answer', '')
                        errors = []
                        if case.get('requires_missing_core_opening') and not text.startswith('I cannot establish'):
                            errors.append('missing_core_opening')
                        for label in case.get('expected_missing', []):
                            if label not in result.get('missing_information', []):
                                errors.append('missing_label:' + label)
                        for heading in ('What is established', 'What is not established', 'Needed from you', 'Next step'):
                            if text.count('**' + heading + '**') != 1:
                                errors.append('section_contract:' + heading)
                        for term in case.get('required_answer_terms', []):
                            if term.casefold() not in text.casefold():
                                errors.append('missing_answer_term:' + term)
                        for term in case.get('forbidden_followup_terms', []):
                            if any(term.casefold() in question.casefold() for question in result.get('suggested_followups', [])):
                                errors.append('tangential_followup:' + term)
                        if not result.get('citations'):
                            errors.append('no_verified_citation')
                        for title in case.get('required_citation_titles', []):
                            if not any(title.casefold() in citation.get('document_title', '').casefold()
                                       for citation in result.get('citations', [])):
                                errors.append('missing_primary_citation:' + title)
                        item = {'case': case['id'], 'run': run + 1, 'passed': not errors,
                                'errors': errors, 'result': result}
                    except Exception as exc:
                        item = {'case': case['id'], 'run': run + 1, 'passed': False,
                                'errors': ['execution:' + type(exc).__name__]}
                    results.append(item)
                    if args.report:
                        Path(args.report).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
                    print(json.dumps({key: item[key] for key in ('case', 'run', 'passed', 'errors')}), flush=True)
    return all(item['passed'] for item in results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', required=True)
    parser.add_argument('--user-id', required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--report')
    args = parser.parse_args()
    if not 3 <= args.repeats <= 10:
        parser.error('--repeats must be between 3 and 10')
    load_dotenv('.env', override=True)
    logging.disable(logging.CRITICAL)  # Never echo provider credentials or database URLs.
    raise SystemExit(0 if asyncio.run(evaluate(args)) else 1)


if __name__ == '__main__':
    main()
