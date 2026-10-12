"""Render a reviewed acceptance run; never assign accuracy scores automatically.

Usage: python scripts/render_mfb_evaluation.py RUN_DIRECTORY REVIEW_JSON OUTPUT_MD
The review JSON must identify the exact corpus snapshot and score every first run.
Raw answers/traces stay in the run directory; portable scorecard and CSV are generated.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def render(directory, review_path, output):
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    review = json.loads(review_path.read_text(encoding='utf-8'))
    if not manifest.get('finished_at'):
        raise ValueError('Run is not finished; do not publish partial counts as final')
    if review['corpus_sha256'] != manifest['corpus']['sha256']:
        raise ValueError('Review does not match the corpus snapshot')
    records = [json.loads((directory / r['file']).read_text(encoding='utf-8')) for r in manifest['runs']]
    first = {r['id']: r for r in records if r['repeat'] == 1}
    scores = {r['id']: r for r in review['scores']}
    if len(scores) != len(review['scores']):
        raise ValueError('Duplicate reviewed question ID')
    if set(first) != set(scores):
        raise ValueError('Every first-run answer must have an explicit reviewed score')
    valid = {'correct', 'partially correct', 'wrong'}
    if any(s['score'] not in valid or not isinstance(s['critical_failure'], bool) for s in scores.values()):
        raise ValueError('Invalid score or missing critical-failure review')
    counts = Counter(s['score'] for s in scores.values())
    summary = {
        'run_directory': str(directory.resolve()), 'started_at': manifest['started_at'],
        'finished_at': manifest['finished_at'], 'corpus': manifest['corpus'],
        'reviewer': review['reviewer'], 'review_limits': review['review_limits'],
        'unique_questions': len(first), 'total_runs': len(records), 'counts': dict(counts),
        'critical_failures': sum(s['critical_failure'] for s in scores.values()),
        'scores': [],
    }
    for case_id, record in sorted(first.items()):
        result = record.get('result', {})
        summary['scores'].append({**scores[case_id], 'seconds': record['seconds'],
            'answer_sha256': hashlib.sha256(result.get('answer', '').encode()).hexdigest(),
            'trace_steps': len(result.get('agent_trace', [])), 'persistence': record.get('persistence'),
            'raw_record': f'q{case_id:02d}-run1.json'})
    (directory / 'scored-results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    with (directory / 'scored-results.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'score', 'critical_failure', 'reason', 'seconds', 'answer_sha256'])
        writer.writeheader()
        writer.writerows({k: s[k] for k in writer.fieldnames} for s in summary['scores'])

    lines = [f"# Iroko MFB acceptance baseline — {review['report_date']}", '',
        f"Result: **{counts['correct']} correct, {counts['partially correct']} partially correct, {counts['wrong']} wrong** across {len(first)} unique questions; {len(records)} total live runs.", '',
        f"**Critical failures identified: {summary['critical_failures']}.** This is a count from this bounded review, not a claim that hallucinations are impossible.", '',
        '## Scope and method', '', manifest['scope'], '', manifest['isolation_limits'], '',
        f"Corpus: {manifest['corpus']['documents']} indexed documents, {manifest['corpus']['chunks']} chunks; " + ', '.join(f'{k}: {v}' for k,v in manifest['corpus']['regulators'].items()) + '.', '',
        f"Started {manifest['started_at']}; finished {manifest['finished_at']}. Questions 1, 3, 7 and 11 ran first. Q14 used the actual Q1 conversation. All other questions started fresh; Q1 was repeated twice. Q8 used explicitly fictional transactions.", '',
        'Date interpretation for Q3/Q7, executed on 11 October 2026: a rolling 90-day window starts 13 July 2026; the next calendar quarter is January–March 2027. An answer may clarify an alternative meaning, but must not pretend the time period was never provided. The interrupted run resumed on 12 October against the same saved corpus; remaining live web checks used their actual execution time.', '',
        review['model_note'], '', review['reviewer'] + '. ' + review['review_limits'], '',
        'Scores assess both supported content and completion of the requested task. An honest partial answer is not a full pass. Wrong routing or task failure is recorded separately from invented authority. Automated persistence checks are not legal accuracy checks.', '',
        '## Scorecard', '', '| Q | Result | Critical | Reason |', '|---|---|---|---|']
    for case_id, score in sorted(scores.items()):
        lines.append(f"| {case_id} | {score['score']} | {'Yes' if score['critical_failure'] else 'No identified'} | {score['reason'].replace('|', '/')} |")
    audit_paragraphs = [line for paragraph in review['repeat_and_audit'] for line in (paragraph, '')]
    lines += ['', '## Repeatability and audit', '', *audit_paragraphs,
              '## Prioritised gaps', '', *[f'{i}. {x}' for i,x in enumerate(review['gaps'],1)], '',
              '## Source-text review', '', *review['source_review'], '',
              '## Evidence files', '',
              f"Raw run folder: `{directory.resolve()}`.", '',
              'This folder contains the corpus snapshot, run manifest, exact answers, citations, SSE events, captured evidence/model draft-and-audit outputs, saved stage traces, synthetic conversation database, reviewed scores and CSV. The captured outputs are observable application data, not hidden model chain-of-thought.', '',
              f"Corpus SHA-256: `{manifest['corpus']['sha256']}`.", '',
              f"Git HEAD: `{manifest['code']['head']}` with the dirty-worktree list and Python-source hash recorded in `manifest.json`. This was not a deployed-production browser test. No code was pushed and no production/customer records were changed by the evaluation.", '',
              '## Use in pilot or application material', '',
              'Describe this as an internal, source-reviewed baseline on 14 fixed questions with synthetic institutional facts. Do not present it as independent legal certification, a statistically representative accuracy rate, or proof of production reliability. Preserve failures alongside passes. A compliance practitioner should review the results before external accuracy claims.', '']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    answers = ['# Exact Iroko answers and citation locators', '', 'Unedited baseline answers; see scored-results.json for assessment.', '']
    for record in records:
        result = record.get('result', {})
        answers += [f"## Q{record['id']} — run {record['repeat']}", '', record['question'], '',
                    result.get('answer') or f"No answer. Error: {record.get('error_type', 'unknown')}", '', '### Sources', '']
        for index, citation in enumerate(result.get('citations', []), 1):
            p = citation.get('provenance') or {}
            url = citation.get('source_url') or p.get('source_url') or ''
            title = re.sub(r'\s+', ' ', citation.get('document_title', 'Untitled'))
            page = f"PDF page {p['page_start']}" if p.get('page_start') else None
            if page and p.get('page_end') and p['page_end'] != p['page_start']:
                page += f"–{p['page_end']}"
            locator = ', '.join(str(x) for x in [p.get('reference_number'), p.get('published_date'), page] if x)
            answers.append(f'{index}. [{title}]({url})' + (f' — {locator}' if locator else ''))
        answers += ['', '### Saved activity', '']
        for event in result.get('agent_trace', []):
            answers.append(f"- {event.get('timestamp', '')} — {event.get('agent', '')}/{event.get('tool', '')}: {event.get('description', '')}")
        answers.append('')
    (directory / 'answers-and-audit.md').write_text('\n'.join(answers), encoding='utf-8')
    print(json.dumps({'scorecard': str(output.resolve()), 'counts': dict(counts), 'critical_failures': summary['critical_failures']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('review', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    render(args.directory, args.review, args.output)
