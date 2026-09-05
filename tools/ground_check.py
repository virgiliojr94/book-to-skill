#!/usr/bin/env python3
"""Ground a generated skill in the extracted source text (fidelity gate).

Companion to scan_generated_skill.py: the security scanner looks for prompt
injection; this checker verifies that what the skill asserts about the book
actually appears in the extracted full text, and that a number agrees with the
list that follows it. It exists because one-shot generation of chapter
summaries (Step 7) can fill a demanded 'Worked Example' slot or a taxonomy
count from the model's memory instead of from the chapter text it was given.

Checks:
  * claim audit - every grounding claim's terms must occur inside the line
    span of its declared chapter in the source (form-feed page breaks never
    merge, so a phrase cannot be found across a page boundary).
  * worked-example provenance - a chapter file that contains a 'Worked
    Example' section must have at least one grounding claim recording terms
    for it (forces the generator to state where the example came from).
  * count-vs-list - 'two prescriptive (Design, Planning, Positioning)' lists
    three items; when a numeral introduces a parenthesised list of a different
    size this is a memory error, not a style choice.

Usage: python3 tools/ground_check.py SKILL_DIR --source FULL_TEXT --grounding GROUNDING_JSON

grounding.json is written by the generator beside full_text.txt in the work
directory (see Step 7 / Step 9.5b of SKILL.md):

  {
    'chapters': {'01': {'start': 1183, 'end': 4152, 'title': 'The ...'}, ...},
    'claims':   [{'id': 'c01', 'chapter': '01', 'claim': '...', 'terms': [...]}]
  }

start/end are 1-based inclusive line numbers in full_text.txt.

Exit status: 0 = grounded, 1 = findings to fix against the source, 2 = bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Finding:
    """One fidelity error: kind, file, 1-based line, and a fixable message."""

    kind: str
    path: str
    line: int
    message: str


class GroundingError(Exception):
    """Raised when the inputs cannot be read or the manifest is malformed."""


NUMERALS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
}

_WS = re.compile(r'\s+')
_COUNT_LIST = re.compile(
    r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,2})\s+'
    r'([A-Za-z][A-Za-z -]{1,60}?)\s*\(([^()\n]*)\)'
)
_WORKED_EXAMPLE_HEADING = re.compile(r'^#+\s*Worked Example\b', re.MULTILINE)
_CHAPTER_FILE = re.compile(r'ch(\d+)')
_ALL_MD = ('glossary.md', 'patterns.md', 'cheatsheet.md', 'SKILL.md')


def _norm(text):
    """Collapse whitespace runs to single spaces, lowercased, for term search."""
    return _WS.sub(' ', text).strip().lower()


def _numeral_to_int(token):
    if token.isdigit():
        return int(token)
    return NUMERALS.get(token.lower())


def _chapter_number(name):
    match = _CHAPTER_FILE.search(name)
    return str(int(match.group(1))) if match else None


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise GroundingError('cannot read %s: %s' % (path, exc))


def _load_source(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        raise GroundingError('cannot read source %s: %s' % (path, exc))


def _page_line_ranges(pages):
    """Return (start_line, end_line) per page; lines are 1-based and inclusive."""
    ranges = []
    cursor = 1
    for page in pages:
        count = len(page.splitlines())
        if count:
            ranges.append((cursor, cursor + count - 1))
            cursor += count
        else:
            ranges.append((cursor, cursor - 1))
    return ranges


def _spans_overlap(page_start, page_end, span_start, span_end):
    return page_start <= span_end and page_end >= span_start


def _split_list_items(inner):
    """Split a parenthesised list on top-level commas, honouring one final
    ' and ' (e.g. '(a, b and c)' is three items). Returns [] when ambiguous."""
    items = [part.strip() for part in inner.split(',')]
    items = [item for item in items if item]
    if not items:
        return []
    if len(items) > 1 and ' and ' in items[-1] and items[-1].count(' and ') == 1:
        head, tail = items[-1].split(' and ', 1)
        items = items[:-1] + [head.strip(), tail.strip()]
    return [item for item in items if len(item) > 1]


def audit_claims(manifest, pages, ranges):
    """Verdict per claim: SUPPORTED / WRONG_CHAPTER / UNFOUND (as Findings)."""
    findings = []
    chapters = manifest.get('chapters') or {}
    claims = manifest.get('claims') or []
    if not isinstance(chapters, dict):
        raise GroundingError('grounding chapters must be an object')
    chapter_ids = {str(int(key)): value for key, value in chapters.items()}
    normalized = [_norm(page) for page in pages]
    for claim in claims:
        claim_id = claim.get('id', '?')
        expected = str(int(claim.get('chapter', '0')))
        span = chapter_ids.get(expected)
        if span is None:
            findings.append(Finding(
                'ERROR', 'grounding.json', 0,
                'claim %s declares chapter %s which has no span in the manifest'
                % (claim_id, expected)))
            continue
        span_start, span_end = int(span['start']), int(span['end'])
        terms = [t for t in (claim.get('terms') or []) if t.strip()]
        found_expected = False
        found_elsewhere = set()
        for idx, page_norm in enumerate(normalized):
            page_start, page_end = ranges[idx]
            if not _spans_overlap(page_start, page_end, span_start, span_end):
                continue
            if any(_norm(t) and _norm(t) in page_norm for t in terms):
                found_expected = True
                break
        if not found_expected:
            for idx, page_norm in enumerate(normalized):
                page_start, page_end = ranges[idx]
                for other_id, other in chapter_ids.items():
                    if other_id == expected:
                        continue
                    o_start, o_end = int(other['start']), int(other['end'])
                    if not _spans_overlap(page_start, page_end, o_start, o_end):
                        continue
                    if any(_norm(t) and _norm(t) in page_norm for t in terms):
                        found_elsewhere.add(other_id)
        if not found_expected and found_elsewhere:
            where = ', '.join(sorted(found_elsewhere))
            findings.append(Finding(
                'ERROR', 'grounding.json', 0,
                'WRONG_CHAPTER %s: expected chapter %s but terms occur only in '
                'chapter(s) %s: %s' % (claim_id, expected, where, claim.get('claim', ''))))
        elif not found_expected:
            findings.append(Finding(
                'ERROR', 'grounding.json', 0,
                'UNFOUND %s: chapter %s text contains none of the claimed terms '
                '(%s) - %s' % (claim_id, expected, ', '.join(terms) or '(no terms)',
                               claim.get('claim', ''))))
    return findings


def audit_worked_examples(manifest, skill_dir, findings):
    """A 'Worked Example' section must have at least one grounding claim whose
    chapter it belongs to, so the generator has stated what to verify."""
    chapters = manifest.get('chapters') or {}
    expected_ids = {str(int(key)) for key in chapters}
    claimed_ids = {str(int(c.get('chapter', '0'))) for c in (manifest.get('claims') or [])}
    chapter_dir = skill_dir / 'chapters'
    if not chapter_dir.is_dir():
        return
    for file in sorted(chapter_dir.glob('*.md')):
        text = file.read_text(encoding='utf-8', errors='replace')
        heading = _WORKED_EXAMPLE_HEADING.search(text)
        if not heading:
            continue
        number = _chapter_number(file.name)
        if number is None or number not in expected_ids:
            continue
        if number not in claimed_ids:
            line = text[: heading.start()].count('\n') + 1
            findings.append(Finding(
                'ERROR', str(file.relative_to(skill_dir)), line,
                'no grounding terms recorded for the Worked Example in chapter %s'
                % number))


def audit_count_lists(skill_dir, findings):
    """Scan every Markdown file for 'N word (a, b, c)' where the list size and
    the numeral disagree - the count was produced from memory, not the text."""
    files = [skill_dir / name for name in _ALL_MD if (skill_dir / name).is_file()]
    chapter_dir = skill_dir / 'chapters'
    if chapter_dir.is_dir():
        files += sorted(chapter_dir.glob('*.md'))
    for file in files:
        try:
            text = file.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in _COUNT_LIST.finditer(line):
                expected = _numeral_to_int(match.group(1))
                if expected is None or expected > 15:
                    continue
                items = _split_list_items(match.group(3))
                if len(items) < 2:
                    continue
                if len(items) != expected:
                    headword = ' '.join(match.group(2).split())
                    findings.append(Finding(
                        'ERROR', str(file.relative_to(skill_dir)), line_no,
                        'counts %s %s but lists %d item(s): %s'
                        % (expected, headword, len(items), ', '.join(items[:8]))))


def ground_skill(skill_dir, source, grounding):
    """Audit a generated skill dir against the source and grounding manifest."""
    skill_dir = Path(skill_dir)
    manifest = _load_json(grounding)
    if 'chapters' not in manifest:
        raise GroundingError('grounding manifest has no chapters object')
    pages = _load_source(source).split('\f')
    ranges = _page_line_ranges(pages)
    findings = []
    findings.extend(audit_claims(manifest, pages, ranges))
    audit_worked_examples(manifest, skill_dir, findings)
    audit_count_lists(skill_dir, findings)
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('path', help='Generated skill directory')
    parser.add_argument('--source', required=True, help='Extracted full_text.txt')
    parser.add_argument('--grounding', required=True, help='grounding.json manifest')
    args = parser.parse_args(argv)
    try:
        findings = ground_skill(args.path, args.source, args.grounding)
    except GroundingError as exc:
        print('ERROR grounding check incomplete: %s' % exc, file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            location = '%s:%s' % (finding.path, finding.line) if finding.line else finding.path
            print('  %s %s %s' % (finding.kind, location, finding.message))
        print('Grounding check found %d finding(s): fix them against the source text, '
              'not by editing the findings away.' % len(findings))
        print('No files were modified by this check.')
        return 1
    print('Grounding check passed: claims land in their chapters and counts match their lists.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
