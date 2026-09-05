'''RED tests for tools/ground_check.py: the source-fidelity gate.
Synthetic fixtures only - no copyrighted text. Each test builds a tiny extracted
full_text (form feed = PDF page break) plus a grounding manifest and asserts the
grounding verdicts and exit codes.
'''
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import ground_check as gc

NL = chr(10)  # newline
FF = chr(12)  # form feed: PDF page break in extracted text


def write_skill(tmp_path, chapter_text, glossary_text=None):
    """Write a minimal generated-skill layout; returns the skill dir."""
    skill = tmp_path / 'skill'
    (skill / 'chapters').mkdir(parents=True)
    (skill / 'chapters' / 'ch01-example.md').write_text(chapter_text, encoding='utf-8')
    if glossary_text is not None:
        (skill / 'glossary.md').write_text(glossary_text, encoding='utf-8')
    return skill


def write_grounding(tmp_path, chapters, claims):
    g = {'chapters': chapters, 'claims': claims}
    p = tmp_path / 'grounding.json'
    p.write_text(json.dumps(g), encoding='utf-8')
    return p


def write_source(tmp_path, pages):
    """pages: list of page strings; joined with form feeds."""
    p = tmp_path / 'full_text.txt'
    p.write_text(FF.join(pages), encoding='utf-8')
    return p


def run_ground(skill, source, grounding):
    return gc.ground_skill(skill, source, grounding)


def test_clean_skill_exits_zero(tmp_path):
    source = write_source(tmp_path, ['alpha the brave', 'beta gamma delta'])
    chapters = {'1': {'start': 1, 'end': 1, 'title': 'One'}}
    claims = [{'id': 'c1', 'chapter': '1', 'claim': 'alpha claim', 'terms': ['alpha the brave']}]
    grounding = write_grounding(tmp_path, chapters, claims)
    md = NL.join(['# Chapter 1: One', '', '## Worked Example', 'alpha the brave story'])
    skill = write_skill(tmp_path, md)
    findings = run_ground(skill, source, grounding)
    assert findings == []
    assert gc.main([str(skill), '--source', str(source), '--grounding', str(grounding)]) == 0


def test_imported_case_is_unfound(tmp_path):
    # The F1 class: chapter text has no such case, the skill imports one anyway.
    source = write_source(tmp_path, ['alpha the brave', 'beta gamma delta'])
    chapters = {'1': {'start': 1, 'end': 2, 'title': 'One'}}
    claims = [{'id': 'c1', 'chapter': '1', 'claim': 'imported story', 'terms': ['Tennessee Valley Authority']}]
    grounding = write_grounding(tmp_path, chapters, claims)
    md = NL.join(['# Chapter 1: One', '', '## Worked Example', 'An imported case study'])
    skill = write_skill(tmp_path, md)
    findings = run_ground(skill, source, grounding)
    assert any('UNFOUND' in f.message for f in findings), findings
    assert gc.main([str(skill), '--source', str(source), '--grounding', str(grounding)]) == 1


def test_wrong_chapter_is_rejected(tmp_path):
    # The F4 class: the case is in the book, but in a different chapter.
    source = write_source(tmp_path, ['alpha text', 'beta National Film Board text'])
    chapters = {'1': {'start': 1, 'end': 1, 'title': 'One'}, '2': {'start': 2, 'end': 2, 'title': 'Two'}}
    claims = [{'id': 'c1', 'chapter': '1', 'claim': 'film board in ch1', 'terms': ['National Film Board']}]
    grounding = write_grounding(tmp_path, chapters, claims)
    md = NL.join(['# Chapter 1: One', '', '## Worked Example', 'film story'])
    skill = write_skill(tmp_path, md)
    findings = run_ground(skill, source, grounding)
    assert any('WRONG_CHAPTER' in f.message for f in findings), findings


def test_phrase_across_page_break_is_not_merged(tmp_path):
    source = write_source(tmp_path, ['alpha the', 'new world beta'])
    chapters = {'1': {'start': 1, 'end': 2, 'title': 'One'}}
    claims = [{'id': 'c1', 'chapter': '1', 'claim': 'cross page', 'terms': ['the new']}]
    grounding = write_grounding(tmp_path, chapters, claims)
    md = '# Chapter 1: One'
    skill = write_skill(tmp_path, md)
    findings = run_ground(skill, source, grounding)
    assert any('UNFOUND' in f.message for f in findings), findings


def test_worked_example_without_grounding_terms_is_rejected(tmp_path):
    # A chapter reproduces a worked example but the manifest records no terms for it.
    source = write_source(tmp_path, ['alpha text'])
    chapters = {'1': {'start': 1, 'end': 1, 'title': 'One'}}
    grounding = write_grounding(tmp_path, chapters, [])
    md = NL.join(['# Chapter 1: One', '', '## Worked Example', 'alpha text'])
    skill = write_skill(tmp_path, md)
    findings = run_ground(skill, source, grounding)
    assert any('no grounding terms' in f.message for f in findings), findings


def test_count_vs_list_mismatch_is_rejected(tmp_path):
    # The F3 class: 'two prescriptive (Design, Planning, Positioning)' lists three.
    source = write_source(tmp_path, ['alpha text'])
    chapters = {'1': {'start': 1, 'end': 1, 'title': 'One'}}
    grounding = write_grounding(tmp_path, chapters, [])
    md = NL.join(['# Chapter 1: One', 'two prescriptive (Design, Planning, Positioning) schools'])
    skill = write_skill(tmp_path, md, glossary_text='Ten Schools: two prescriptive (A, B, C)')
    findings = run_ground(skill, source, grounding)
    assert any('counts' in f.message for f in findings), findings
    assert gc.main([str(skill), '--source', str(source), '--grounding', str(grounding)]) == 1


def test_count_vs_list_match_passes(tmp_path):
    source = write_source(tmp_path, ['alpha text'])
    chapters = {'1': {'start': 1, 'end': 1, 'title': 'One'}}
    grounding = write_grounding(tmp_path, chapters, [])
    md = NL.join(['# Chapter 1: One', 'three schools (Design, Planning, Positioning)'])
    skill = write_skill(tmp_path, md)
    findings = run_ground(skill, source, grounding)
    assert findings == []


def test_chapter_without_worked_example_needs_no_claims(tmp_path):
    source = write_source(tmp_path, ['alpha text'])
    chapters = {'1': {'start': 1, 'end': 1, 'title': 'One'}}
    grounding = write_grounding(tmp_path, chapters, [])
    md = '# Chapter 1: One'
    skill = write_skill(tmp_path, md)
    findings = run_ground(skill, source, grounding)
    assert findings == []


def test_missing_inputs_exit_two(tmp_path):
    assert gc.main(['nowhere', '--source', 'nope', '--grounding', 'nada']) == 2
