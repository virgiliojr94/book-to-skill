"""Sample headings stay inside longer Markdown fences until a valid closer."""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import _closed_fence_line_numbers, detect_structure, main


@pytest.mark.parametrize("marker", ["`", "~"])
def test_shorter_marker_does_not_close_outer_fence(marker):
    lines = [
        "before",
        marker * 4 + "markdown",
        marker * 3,
        "## Sample title",
        marker * 3,
        marker * 4,
        "after",
    ]

    assert _closed_fence_line_numbers(lines) == set(range(1, 6))


@pytest.mark.parametrize("marker", ["`", "~"])
def test_marker_with_info_string_cannot_close_fence(marker):
    lines = [marker * 3, marker * 4 + "python", "## Sample title", marker * 3]

    assert _closed_fence_line_numbers(lines) == {0, 1, 2, 3}


@pytest.mark.parametrize("marker", ["`", "~"])
def test_shorter_marker_without_valid_closer_keeps_unclosed_policy(marker):
    # The extractor deliberately leaves truly unclosed blocks reachable.
    assert _closed_fence_line_numbers([marker * 4, "text", marker * 3]) == set()


@pytest.mark.parametrize("marker", ["`", "~"])
def test_longer_closer_with_whitespace_is_valid(marker):
    lines = ["  " + marker * 3 + "python", "code", " " + marker * 5 + " \t"]

    assert _closed_fence_line_numbers(lines) == {0, 1, 2}


def _handbook(sample):
    return (
        "# Handbook\n\n## Alpha\nFirst real section.\n\n"
        "````markdown\n```python\n"
        f"{sample}\n"
        "```\n````\n\n## Beta\nSecond real section.\n"
    )


def test_structural_scan_ignores_headings_inside_nested_fence_example():
    structure = detect_structure(_handbook("## Sample title"))

    assert structure["chapters_detected"] == 2
    assert structure["chapters_method"] == "structural"
    assert structure["chapter_headings_sample"] == ["## Alpha", "## Beta"]


def test_numeric_scan_ignores_chapter_examples_inside_nested_fence():
    structure = detect_structure(_handbook("Chapter 7 Example\nChapter 8 Example"))

    assert structure["chapters_detected"] == 2
    assert structure["chapters_method"] == "structural"
    assert structure["chapter_headings_sample"] == ["## Alpha", "## Beta"]


def test_cli_records_real_chapters_without_removing_code_sample(tmp_path, monkeypatch):
    source = tmp_path / "handbook.md"
    text = _handbook("## Sample title")
    source.write_text(text, encoding="utf-8")
    output_dir = tmp_path / "output"

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
    assert corpus.endswith(text.rstrip())
    for record in [metadata, metadata["sources"][0]]:
        assert record["chapters_detected"] == 2
        assert record["chapters_method"] == "structural"
        assert record["chapter_headings_sample"] == ["## Alpha", "## Beta"]
