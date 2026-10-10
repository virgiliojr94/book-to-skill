"""RTF escaped backslashes must not become active controls in the fallback."""

import json
import sys

import pytest

from book_to_skill.parsers.rtf import strip_rtf_fallback
from book_to_skill.utils import estimate_tokens, main


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r"{\rtf1 Show \\u945? literally.}", r"Show \u945? literally."),
        (r"{\rtf1 Show \\'e9 literally.}", r"Show \'e9 literally."),
        (r"{\rtf1 Show \\par literally.}", r"Show \par literally."),
        (r"{\rtf1 Show \\pard literally.}", r"Show \pard literally."),
        (r"{\rtf1 Show \\tab literally.}", r"Show \tab literally."),
        (r"{\rtf1 Path C:\\table\\part}", r"Path C:\table\part"),
        (r"{\rtf1 Two \\\\u945? slashes.}", r"Two \\u945? slashes."),
        (r"{\rtf1 Slash \\\u945? then alpha.}", "Slash \\α then alpha."),
        (
            r"{\rtf1 Literal \\ansicpg1251 and caf\'e9.}",
            r"Literal \ansicpg1251 and café.",
        ),
    ],
)
def test_escaped_backslash_keeps_control_shaped_text_literal(raw, expected):
    assert strip_rtf_fallback(raw) == expected


def test_literal_and_active_controls_coexist_after_destination_stripping():
    raw = (
        r"{\rtf1\ansi {\fonttbl{\f0 Hidden Font;}}"
        r"Literal \{\\u945?\}, active \u945? and caf\'e9."
        r"\par Path C:\\table\\part\tab end.}"
    )

    assert strip_rtf_fallback(raw) == (
        "Literal {\\u945?}, active α and café.\n"
        " Path C:\\table\\part\t end."
    )


def test_cli_persists_literal_controls_and_source_metrics(tmp_path, monkeypatch):
    source = tmp_path / "literal-controls.rtf"
    source.write_text(
        r"{\rtf1\ansi Chapter 1\par"
        r"Show \\u945? and \\'e9 literally.\par"
        r"Path C:\\table\\part\tab end.}",
        encoding="utf-8",
    )
    expected = (
        "Chapter 1\n"
        "Show \\u945? and \\'e9 literally.\n"
        "Path C:\\table\\part\t end."
    )
    output_dir = tmp_path / "output"

    # Exercise the real fallback even if the optional parser is installed.
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
    assert corpus.endswith(expected)
    assert metadata["extraction_method"] == "rtf-regex"
    recorded_source = metadata["sources"][0]
    assert recorded_source["extraction_method"] == "rtf-regex"
    assert recorded_source["chars"] == len(expected)
    assert recorded_source["words"] == len(expected.split())
    assert recorded_source["estimated_tokens"] == estimate_tokens(expected)
    assert metadata["chars"] == len(corpus)
    assert metadata["words"] == len(corpus.split())
