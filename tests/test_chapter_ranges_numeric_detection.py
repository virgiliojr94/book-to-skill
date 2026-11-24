"""`chapter_ranges` must be built for numeric and structural detection too.

Only the PDF-outline path published `chapter_titles`, and the consolidation step
built top-level `chapter_ranges` solely for `chapters_method == "outline"`. So a
book whose chapters were found by the numeric or structural scan got
`chapters_detected: 8` and no ranges at all, and Step 7 of `SKILL.md` ("use
top-level `chapter_ranges` ... otherwise grep for chapter headings") always took
the grep fallback. That fallback lands on the ToC rows, which are the first
matches in the text, not the body headings. (Issue #348)

The titles have to be the *body* headings. A book whose ToC and body both carry
"Chapter 1. Alpha" produces two entries during detection, and the ToC row keeps
its leader and page number -- a string `chapter_line_ranges` can never match,
because `_is_disqualified_chapter_line` rejects leader rows. Keeping the last
occurrence per chapter number yields the clean body title.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import chapter_line_ranges, detect_structure, main

# A ToC whose rows carry dot leaders and page numbers, then the body headings.
TOC_AND_BODY = (
    "Contents\n\n"
    "Chapter 1. Alpha ........ 9\n"
    "Chapter 2. Beta ......... 25\n\n"
    "Chapter 1. Alpha\n\n"
    "Opening of the first chapter.\nStill the first chapter.\n\n"
    "Chapter 2. Beta\n\n"
    "Opening of the second chapter.\n"
)
STRUCTURAL = (
    "# Book Title\n\n"
    "## Alpha\n\nFirst section body.\n\n"
    "## Beta\n\nSecond section body.\n"
)


def _run(tmp_path, monkeypatch, text, suffix=".md"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / f"book{suffix}"
    source.write_text(text, encoding="utf-8")
    out_dir = tmp_path / "out"
    out_meta = out_dir / "metadata.json"
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(out_dir))
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", out_dir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", out_dir / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", out_meta)
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)
    monkeypatch.setattr("sys.argv", ["extract.py", str(source), "--install-missing", "no"])

    main()
    return (
        json.loads(out_meta.read_text(encoding="utf-8")),
        (out_dir / "full_text.txt").read_text(encoding="utf-8"),
    )


class TestNumericChapterTitles:
    def test_numeric_detection_publishes_body_titles(self):
        """The ToC rows are detected as headings but must not become titles."""
        structure = detect_structure(TOC_AND_BODY)

        assert structure["chapters_method"] == "numeric"
        assert structure["chapter_titles"] == ["Chapter 1. Alpha", "Chapter 2. Beta"]

    def test_toc_rows_are_still_in_the_sample(self):
        """Guards the premise: detection does see both copies of each heading."""
        sample = detect_structure(TOC_AND_BODY)["chapter_headings_sample"]

        assert "Chapter 1. Alpha ........ 9" in sample
        assert sample.count("Chapter 1. Alpha") == 1

    def test_structural_detection_publishes_titles(self):
        structure = detect_structure(STRUCTURAL)

        assert structure["chapters_method"] == "structural"
        assert structure["chapter_titles"] == ["## Alpha", "## Beta"]

    def test_no_titles_key_without_chapters(self):
        """Back-compat: the key is absent, not empty, when nothing is detected."""
        structure = detect_structure("Just prose, no headings at all.\n")

        assert structure["chapters_method"] == "none"
        assert "chapter_titles" not in structure

    def test_markdown_prefixed_numeric_headings_round_trip(self):
        """A converted ebook's "## Chapter 1: Alpha" must still resolve."""
        text = "## Chapter 1: Alpha\n\nbody a\n\n## Chapter 2: Beta\n\nbody b\n"
        titles = detect_structure(text)["chapter_titles"]

        ranges = chapter_line_ranges(text, titles)
        assert [r["start_line"] for r in ranges] == [1, 5]


class TestRangesAnchorOnTheBody:
    def test_ranges_skip_the_toc_rows(self):
        titles = detect_structure(TOC_AND_BODY)["chapter_titles"]
        lines = TOC_AND_BODY.splitlines()

        ranges = chapter_line_ranges(TOC_AND_BODY, titles)
        assert [lines[r["start_line"] - 1] for r in ranges] == [
            "Chapter 1. Alpha",
            "Chapter 2. Beta",
        ]
        # Ranges are inclusive and contiguous: chapter 1 ends on the line
        # before chapter 2 starts, so the body is covered without overlap.
        assert ranges[0]["end_line"] == ranges[1]["start_line"] - 1

    def test_bare_toc_rows_still_anchor_on_the_toc(self):
        """Known ceiling, pinned so a later fix is a visible change.

        When the page number sits on its own line the ToC row *equals* the body
        heading, so the forward search matches the ToC copy first and the last
        range swallows the body. Skipping the ToC region is the documented
        follow-up; it needs a corpus to tune, so it is not guessed at here.
        """
        text = (
            "Contents\n\nChapter 1. Alpha\n9\nChapter 2. Beta\n25\n\n"
            "Chapter 1. Alpha\n\nbody a\n\nChapter 2. Beta\n\nbody b\n"
        )
        titles = detect_structure(text)["chapter_titles"]

        ranges = chapter_line_ranges(text, titles)
        assert ranges[0]["start_line"] == 3  # the ToC row, not line 8


class TestMetadataGetsRanges:
    def test_numeric_metadata_has_top_level_ranges(self, tmp_path, monkeypatch):
        """The exact gap in the report: numeric detection, no chapter_ranges."""
        meta, full_text = _run(tmp_path, monkeypatch, TOC_AND_BODY)

        assert meta["chapters_method"] == "numeric"
        ranges = meta["chapter_ranges"]
        assert [r["title"] for r in ranges] == ["Chapter 1. Alpha", "Chapter 2. Beta"]
        # Ranges are 1-based inclusive line numbers into full_text.txt, which
        # carries a SOURCE banner the detection text does not.
        lines = full_text.splitlines()
        assert lines[ranges[0]["start_line"] - 1] == "Chapter 1. Alpha"
        assert lines[ranges[1]["start_line"] - 1] == "Chapter 2. Beta"

    def test_structural_metadata_has_top_level_ranges(self, tmp_path, monkeypatch):
        meta, full_text = _run(tmp_path, monkeypatch, STRUCTURAL)

        assert meta["chapters_method"] == "structural"
        lines = full_text.splitlines()
        starts = [r["start_line"] for r in meta["chapter_ranges"]]
        assert [lines[s - 1] for s in starts] == ["## Alpha", "## Beta"]

    def test_per_source_record_also_has_ranges(self, tmp_path, monkeypatch):
        meta, _ = _run(tmp_path, monkeypatch, TOC_AND_BODY)

        source = meta["sources"][0]
        assert [r["title"] for r in source["chapter_ranges"]] == [
            "Chapter 1. Alpha",
            "Chapter 2. Beta",
        ]
