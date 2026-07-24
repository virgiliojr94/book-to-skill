import json
import sys
from unittest import mock

import pytest

from book_to_skill.exceptions import ExtractionError
from book_to_skill.sanitize import sanitize_extracted_text
from book_to_skill.utils import extract_single_file, main


INVISIBLE_CODEPOINTS = (
    "\u200b"
    "\u200c"
    "\u200d"
    "\ufeff"
    "\U000e0000"
    "\U000e0069"
    "\U000e007f"
)


def test_sanitizer_removes_zero_width_and_tag_block_codepoints():
    sanitized, removed = sanitize_extracted_text(
        f"before{INVISIBLE_CODEPOINTS}after"
    )

    assert sanitized == "beforeafter"
    assert removed == len(INVISIBLE_CODEPOINTS)


def test_sanitizer_preserves_normal_multilingual_text_byte_for_byte():
    original = "Cafe\u0301 - \u4e2d\u6587 - \U0001f642 - plain ASCII\n"

    sanitized, removed = sanitize_extracted_text(original)

    assert sanitized == original
    assert sanitized.encode("utf-8") == original.encode("utf-8")
    assert removed == 0


def test_extract_single_file_sanitizes_before_metrics(tmp_path, capsys):
    source = tmp_path / "source.txt"
    source.write_text(
        "No customer PII\u200b leaves the repo.\U000e0069",
        encoding="utf-8",
    )

    with mock.patch("book_to_skill.utils.prepare_dependencies"):
        result = extract_single_file(source, "text", "no")

    assert result["text"] == "No customer PII leaves the repo."
    assert result["chars"] == len(result["text"])
    assert result["words"] == 6
    captured = capsys.readouterr()
    assert "removed 2 invisible Unicode code point(s)" in captured.err


def test_extract_single_file_rejects_invisible_only_source(tmp_path):
    source = tmp_path / "invisible.txt"
    source.write_text(INVISIBLE_CODEPOINTS, encoding="utf-8")

    with mock.patch("book_to_skill.utils.prepare_dependencies"):
        with pytest.raises(ExtractionError, match="no visible content"):
            extract_single_file(source, "text", "no")


def test_main_writes_only_sanitized_text_and_metrics(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text(
        "Chapter 1\nPolicy\u200b text.\U000e0069",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    output_text = output_dir / "full_text.txt"
    output_meta = output_dir / "metadata.json"

    monkeypatch.setattr(sys, "argv", ["extract.py", str(source)])
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", output_dir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", output_text)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", output_meta)
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *args: None)

    main()

    extracted = output_text.read_text(encoding="utf-8")
    metadata = json.loads(output_meta.read_text(encoding="utf-8"))
    expected_source, _ = sanitize_extracted_text(
        source.read_bytes().decode("utf-8")
    )
    assert "Policy text." in extracted
    assert all(character not in extracted for character in INVISIBLE_CODEPOINTS)
    assert metadata["chars"] == len(extracted)
    assert metadata["sources"][0]["chars"] == len(expected_source)
