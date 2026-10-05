"""Regression tests for the source-fidelity advisory checker."""

import importlib.util
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
spec = importlib.util.spec_from_file_location(
    "check_fidelity",
    TOOLS_DIR / "check_fidelity.py",
)
fidelity = importlib.util.module_from_spec(spec)
sys.modules["check_fidelity"] = fidelity
spec.loader.exec_module(fidelity)

SOURCE = """<<<PAGE 1>>>
前 言
这本书讨论怎样把一本书提炼成技能。
<<<PAGE 2>>>
老石说，开会之前必须想清楚为什么开。他当场批评过一个迟到二十分钟的人。
提到的数字是百分之九十的精力用于调研。
"""


def _write_skill(root: Path, body: str) -> Path:
    chapters = root / "chapters"
    chapters.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: demo\ndescription: demo skill.\n---\n\n# Demo\n\nindex\n",
        encoding="utf-8",
    )
    (chapters / "ch01.md").write_text(body, encoding="utf-8")
    return root


def test_quoted_verbatim_and_fabricated_are_separated(tmp_path):
    skill = _write_skill(
        tmp_path,
        '他说"开会之前必须想清楚为什么开"，还编了一句"这条引文原书没有"。\n',
    )
    report = fidelity.check_fidelity(_book(tmp_path), skill, min_n=12, max_longest=50, limit=25)
    quotes = {e["quote"] for e in report["unverified_quotes"]}
    assert "这条引文原书没有" in quotes
    verified = {e["quote"] for e in fidelity.quoted_claims(
        fidelity._skill_texts(fidelity._skill_files(skill), skill),
        fidelity.normalize(_book_text()),
    )[0]}
    assert "开会之前必须想清楚为什么开" in verified


def test_passage_copying_flagged_and_paraphrase_not(tmp_path):
    copied = "开会之前必须想清楚为什么开。他当场批评过一个迟到二十分钟的人。提到的数字是百分之九十的精力用于调研。"
    skill = _write_skill(tmp_path, copied + "\n")
    report = fidelity.check_fidelity(_book(tmp_path), skill, 12, 50, 25)
    assert report["longest"] >= 30

    other = tmp_path / "skill2"
    _write_skill(other, "开会以前先想明白开会的理由；迟到的处理要看当场情况。\n")
    report2 = fidelity.check_fidelity(_book(tmp_path), other, 12, 50, 25)
    assert report2["longest"] < 12


def test_page_number_is_reported(tmp_path):
    skill = _write_skill(
        tmp_path, "老石说，开会之前必须想清楚为什么开。他当场批评过一个迟到二十分钟的人。\n"
    )
    report = fidelity.check_fidelity(_book(tmp_path), skill, 12, 50, 25)
    assert report["passages"], "expected at least one common passage"
    assert all(p["page"] in (1, 2) for p in report["passages"])


def _book_text() -> str:
    return SOURCE


def _book(tmp_path: Path) -> Path:
    book = tmp_path / "book.txt"
    book.write_text(SOURCE, encoding="utf-8")
    return book
