"""Consolidated `has_toc` must not depend on the order of the input files.

`detect_structure` only scans the first ~30,000 characters for a table-of-contents
header, which is right for one book: a ToC lives in the front matter. But the
consolidated value was derived by re-running that scan over the *joined* corpus,
so the window only ever covered the first source. A ToC in any later book was
invisible, and feeding the same two books in the other order produced the
opposite answer.

`main()` prints a "No table of contents detected" warning off this value and
writes it to metadata.json, where Step 3 uses it to decide whether chapter
mapping can trust a ToC or must fall back to a heading scan alone.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import main

# Long enough that anything after it falls outside the 30k scan window.
FILLER = "Filler prose about distributed systems. " * 1200
NO_TOC_BOOK = "Chapter 1\n" + FILLER + "\n"
TOC_BOOK = "Table of Contents\n\nChapter 2\nBody of the second book.\n"


def _run(tmp_path, monkeypatch, *sources):
    tmp_path.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, text in enumerate(sources, start=1):
        path = tmp_path / f"book{index}.md"
        path.write_text(text, encoding="utf-8")
        paths.append(str(path))

    out_dir = tmp_path / "out"
    out_meta = out_dir / "metadata.json"
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(out_dir))
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", out_dir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", out_dir / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", out_meta)
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)
    monkeypatch.setattr(
        "sys.argv", ["extract.py", *paths, "--install-missing", "no"]
    )

    main()
    return json.loads(out_meta.read_text(encoding="utf-8"))


class TestMultiSourceTocDetection:
    def test_filler_book_pushes_second_book_past_the_window(self):
        """Guards the premise: without this, the test would prove nothing."""
        assert len(NO_TOC_BOOK) > 30000

    def test_toc_in_second_source_is_detected(self, tmp_path, monkeypatch):
        meta = _run(tmp_path, monkeypatch, NO_TOC_BOOK, TOC_BOOK)

        assert meta["total_sources"] == 2
        assert meta["has_toc"] is True

    def test_result_is_independent_of_input_order(self, tmp_path, monkeypatch):
        first = _run(tmp_path / "a", monkeypatch, NO_TOC_BOOK, TOC_BOOK)
        second = _run(tmp_path / "b", monkeypatch, TOC_BOOK, NO_TOC_BOOK)

        assert first["has_toc"] == second["has_toc"] is True

    def test_agrees_with_the_per_source_records(self, tmp_path, monkeypatch):
        meta = _run(tmp_path, monkeypatch, NO_TOC_BOOK, TOC_BOOK)

        per_source = [src["has_toc"] for src in meta["sources"]]
        assert per_source == [False, True]
        assert meta["has_toc"] is any(per_source)

    def test_no_toc_anywhere_stays_false(self, tmp_path, monkeypatch):
        meta = _run(tmp_path, monkeypatch, NO_TOC_BOOK, "Chapter 2\nPlain body.\n")

        assert meta["has_toc"] is False

    def test_single_source_behaviour_unchanged(self, tmp_path, monkeypatch):
        with_toc = _run(tmp_path / "a", monkeypatch, TOC_BOOK)
        without = _run(tmp_path / "b", monkeypatch, NO_TOC_BOOK)

        assert with_toc["has_toc"] is True
        assert without["has_toc"] is False

    def test_chapter_count_still_spans_all_sources(self, tmp_path, monkeypatch):
        """The #83 fix must keep working alongside this one."""
        meta = _run(tmp_path, monkeypatch, NO_TOC_BOOK, TOC_BOOK)

        # Chapter 1 from the first book, Chapter 2 from the second.
        assert meta["chapters_detected"] == 2
