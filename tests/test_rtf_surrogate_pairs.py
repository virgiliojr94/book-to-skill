"""Supplementary Unicode characters survive the dependency-free RTF fallback."""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.rtf import strip_rtf_fallback
from book_to_skill.utils import main


@pytest.mark.parametrize(
    "escapes",
    [
        r"\u-10179?\u-8704?",
        r"\u-10179\'3f\u-8704\'3f",
        r"\u-10179 \u-8704 ",
    ],
)
def test_adjacent_surrogate_escapes_form_one_character(escapes):
    assert strip_rtf_fallback(r"{\rtf1 A " + escapes + " B}") == "A 😀 B"


def test_surrogates_do_not_pair_across_text_or_with_wrong_order():
    raw = r"{\rtf1 A \u-10179?x\u-8704? B \u-8704?\u-10179? C}"
    assert strip_rtf_fallback(raw) == "A x B  C"


def test_multiple_pairs_and_escaped_literal_remain_distinct():
    raw = r"{\rtf1 \u-10179?\u-8704?\u-10179?\u-8704? \\u-10179?}"
    assert strip_rtf_fallback(raw) == r"😀😀 \u-10179?"


def test_cli_writes_combined_character_with_fallback(tmp_path, monkeypatch):
    source = tmp_path / "supplementary.rtf"
    source.write_text(
        r"{\rtf1 Chapter 1\par A \u-10179?\u-8704? B}", encoding="utf-8"
    )
    output_dir = tmp_path / "output"

    monkeypatch.setitem(sys.modules, "striprtf", None)
    monkeypatch.setitem(sys.modules, "striprtf.striprtf", None)
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *args: None)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", output_dir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", output_dir / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", output_dir / "metadata.json")
    monkeypatch.setattr(
        sys, "argv", ["extract.py", str(source), "--install-missing", "no"]
    )

    main()

    corpus = (output_dir / "full_text.txt").read_text(encoding="utf-8")
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert corpus.endswith("Chapter 1\nA 😀 B")
    assert metadata["extraction_method"] == "rtf-regex"
