"""
Test suite for the three PR blocker fixes + nits in the book_to_skill package.

Covers:
  Fix #1 — EPUB extraction tuple-unpack regression
  Fix #2 — Batch resilience (ExtractionError instead of sys.exit)
  Fix #3 — Explicit input order preservation
  Nit   — Glob results filtered by SUPPORTED_EXTENSIONS
"""

import json
import sys
import textwrap
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: make sure the book_to_skill package is importable
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.exceptions import ExtractionError
from book_to_skill.utils import (
    resolve_input_files,
    extract_single_file,
    parse_arguments,
    estimate_tokens,
    detect_structure,
    _cn_numeral_to_int,
    main,
)
from book_to_skill.config import SUPPORTED_EXTENSIONS
from book_to_skill.parsers.docx import extract_docx_with_zipfile
from book_to_skill.parsers.rtf import strip_rtf_fallback


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers – fixture creation
# ═══════════════════════════════════════════════════════════════════════════

def _make_text_file(path: Path, content: str = "Hello world from test file.") -> Path:
    """Create a plain-text .txt file."""
    path.write_text(content, encoding="utf-8")
    return path


def _make_md_file(path: Path, content: str = "# Title\n\nSome markdown content.") -> Path:
    """Create a plain-text .md file."""
    path.write_text(content, encoding="utf-8")
    return path


def _make_html_file(path: Path) -> Path:
    """Create a minimal HTML file."""
    path.write_text(
        "<html><body><h1>Hello</h1><p>Test paragraph.</p></body></html>",
        encoding="utf-8",
    )
    return path


def _make_minimal_epub(path: Path) -> Path:
    """Create a minimal valid EPUB (zip with mimetype + OPF + one xhtml).

    The xhtml entry name must match the OPF ``href`` exactly because
    the stdlib zipfile parser in ``epub.py`` reads hrefs from the OPF
    and looks them up directly as zip entry names.
    """
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "content.opf",
            textwrap.dedent("""\
                <?xml version="1.0"?>
                <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
                  <metadata/>
                  <manifest>
                    <item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
                  </manifest>
                  <spine>
                    <itemref idref="ch1"/>
                  </spine>
                </package>
            """),
        )
        zf.writestr(
            "chapter1.xhtml",
            "<html><body><p>EPUB chapter one content.</p></body></html>",
        )
    return path


def _make_minimal_docx(path: Path) -> Path:
    """Create a minimal valid DOCX (ZIP with word/document.xml)."""
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xml = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="{ns}">
          <w:body>
            <w:p><w:r><w:t>DOCX test paragraph</w:t></w:r></w:p>
          </w:body>
        </w:document>
    """)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
    return path


def _make_unsupported_file(path: Path) -> Path:
    """Create a file with an unsupported extension."""
    path.write_bytes(b"unsupported binary junk data")
    return path


def _make_oebps_epub(path: Path) -> Path:
    """Create an EPUB with OPF inside OEBPS/ (like LibreOffice/Calibre output).

    This is the layout that triggers the OPF-relative href bug:
    the OPF lists ``href="sections/ch1.xhtml"`` but the actual zip entry
    is ``OEBPS/sections/ch1.xhtml``.
    """
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            textwrap.dedent("""\
                <?xml version="1.0"?>
                <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"
                           version="1.0">
                  <rootfiles>
                    <rootfile full-path="OEBPS/content.opf"
                              media-type="application/oebps-package+xml"/>
                  </rootfiles>
                </container>
            """),
        )
        zf.writestr(
            "OEBPS/content.opf",
            textwrap.dedent("""\
                <?xml version="1.0"?>
                <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
                  <metadata/>
                  <manifest>
                    <item id="ch1" href="sections/ch1.xhtml" media-type="application/xhtml+xml"/>
                    <item id="ch2" href="sections/ch2.xhtml" media-type="application/xhtml+xml"/>
                  </manifest>
                  <spine>
                    <itemref idref="ch1"/>
                    <itemref idref="ch2"/>
                  </spine>
                </package>
            """),
        )
        zf.writestr(
            "OEBPS/sections/ch1.xhtml",
            "<html><body><p>Chapter one from OEBPS.</p></body></html>",
        )
        zf.writestr(
            "OEBPS/sections/ch2.xhtml",
            "<html><body><p>Chapter two from OEBPS.</p></body></html>",
        )
    return path



# ═══════════════════════════════════════════════════════════════════════════
#  FIX #1 — EPUB extraction no longer does tuple-unpack
# ═══════════════════════════════════════════════════════════════════════════

class TestEpubExtractionFix:
    """Verify that EPUB extraction works without tuple-unpack errors."""

    def test_epub_extract_with_ebooklib_returns_str_or_none(self):
        """extract_with_ebooklib returns str|None, NOT a tuple."""
        from book_to_skill.parsers.epub import extract_with_ebooklib

        # With ebooklib likely not installed in test env → returns None
        result = extract_with_ebooklib("nonexistent.epub")
        assert result is None or isinstance(result, str), (
            f"extract_with_ebooklib should return str|None, got {type(result)}"
        )

    def test_epub_extraction_via_zipfile_fallback(self, tmp_path):
        """EPUB with zipfile fallback should work end-to-end."""
        epub_path = _make_minimal_epub(tmp_path / "test.epub")

        # Mock prepare_dependencies to be a no-op
        with mock.patch("book_to_skill.utils.prepare_dependencies"):
            result = extract_single_file(epub_path, "text", "no")

        assert result["format"] == "epub"
        assert result["extraction_method"] in ("ebooklib", "zipfile")
        assert "EPUB chapter one content" in result["text"]
        assert result["chars"] > 0
        assert result["words"] > 0

    def test_epub_no_tuple_unpack_error(self, tmp_path):
        """The old bug: tuple-unpack of str/None should not happen."""
        epub_path = _make_minimal_epub(tmp_path / "test.epub")

        # Even if ebooklib is absent, this should NOT raise TypeError/ValueError
        with mock.patch("book_to_skill.utils.prepare_dependencies"):
            try:
                result = extract_single_file(epub_path, "text", "no")
            except (TypeError, ValueError) as exc:
                pytest.fail(f"Tuple-unpack regression! Got: {exc}")

        assert result["text"]  # some text was extracted


# ═══════════════════════════════════════════════════════════════════════════
#  BUG #11 — EPUB OPF-relative href resolution
# ═══════════════════════════════════════════════════════════════════════════

class TestEpubOpfRelativePaths:
    """Verify that EPUBs with OPF in a subdirectory (OEBPS/) are extracted."""

    def test_zipfile_fallback_resolves_oebps_paths(self, tmp_path):
        """The core bug: hrefs in OPF are relative to OPF dir, not archive root."""
        from book_to_skill.parsers.epub import extract_with_zipfile

        epub_path = _make_oebps_epub(tmp_path / "oebps.epub")
        text = extract_with_zipfile(str(epub_path))

        assert text is not None, "extract_with_zipfile returned None for OEBPS EPUB"
        assert "Chapter one from OEBPS" in text
        assert "Chapter two from OEBPS" in text

    def test_full_extraction_with_oebps_epub(self, tmp_path):
        """End-to-end: extract_single_file should succeed with OEBPS layout."""
        epub_path = _make_oebps_epub(tmp_path / "test_oebps.epub")

        with mock.patch("book_to_skill.utils.prepare_dependencies"):
            result = extract_single_file(epub_path, "text", "no")

        assert result["format"] == "epub"
        assert result["extraction_method"] in ("ebooklib", "zipfile")
        assert "Chapter one from OEBPS" in result["text"]
        assert "Chapter two from OEBPS" in result["text"]

    def test_container_xml_locates_opf(self, tmp_path):
        """_find_opf_path should prefer META-INF/container.xml over globbing."""
        from book_to_skill.parsers.epub import _find_opf_path

        epub_path = _make_oebps_epub(tmp_path / "container.epub")
        with zipfile.ZipFile(epub_path) as zf:
            opf_path = _find_opf_path(zf)

        assert opf_path == "OEBPS/content.opf"

    def test_count_chapters_with_oebps(self, tmp_path):
        """count_epub_chapters should work with OPF in subdirectory."""
        from book_to_skill.parsers.epub import count_epub_chapters

        epub_path = _make_oebps_epub(tmp_path / "chapters.epub")
        count = count_epub_chapters(str(epub_path))
        assert count == 2

    def test_root_level_opf_still_works(self, tmp_path):
        """Regression check: root-level OPF (no subdirectory) should still work."""
        from book_to_skill.parsers.epub import extract_with_zipfile

        epub_path = _make_minimal_epub(tmp_path / "root_opf.epub")
        text = extract_with_zipfile(str(epub_path))

        assert text is not None
        assert "EPUB chapter one content" in text


# ═══════════════════════════════════════════════════════════════════════════
#  FIX #2 — Batch resilience (ExtractionError instead of sys.exit)
# ═══════════════════════════════════════════════════════════════════════════

class TestBatchResilience:
    """Verify that a single bad file does NOT abort the entire batch."""

    def test_extract_single_file_raises_on_missing(self, tmp_path):
        """A missing file should raise ExtractionError, not sys.exit."""
        missing = tmp_path / "does_not_exist.txt"
        with pytest.raises(ExtractionError, match="File not found"):
            extract_single_file(missing, "text", "no")

    def test_extract_single_file_raises_on_unsupported(self, tmp_path):
        """An unsupported format should raise ExtractionError, not sys.exit."""
        unsupported = _make_unsupported_file(tmp_path / "data.xyz")
        with pytest.raises(ExtractionError, match="Unsupported format"):
            extract_single_file(unsupported, "text", "no")

    def test_batch_continues_past_bad_files(self, tmp_path):
        """A mix of good + bad files should produce output for the good ones."""
        # Create a valid text file
        good_file = _make_text_file(tmp_path / "good.txt", "Good content here.")
        # Create a file that will fail (unsupported extension, garbage bytes)
        bad_file = _make_unsupported_file(tmp_path / "bad.xyz")

        # Simulate the batch loop from main()
        input_files = [good_file, bad_file]
        extracted = []
        errors = []

        for fp in input_files:
            try:
                with mock.patch("book_to_skill.utils.prepare_dependencies"):
                    res = extract_single_file(fp, "text", "no")
                extracted.append(res)
            except ExtractionError as exc:
                errors.append((fp, str(exc)))

        assert len(extracted) == 1, "Good file should have been extracted"
        assert len(errors) == 1, "Bad file should have been recorded as error"
        assert "Good content here" in extracted[0]["text"]

    def test_batch_fails_hard_when_all_fail(self, tmp_path, monkeypatch):
        """If ALL sources fail, main() should sys.exit(1)."""
        bad1 = _make_unsupported_file(tmp_path / "bad1.xyz")
        bad2 = _make_unsupported_file(tmp_path / "bad2.abc")

        monkeypatch.setattr(
            "sys.argv",
            ["extract.py", str(bad1), str(bad2), "--install-missing", "no"],
        )
        monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_produces_output_with_partial_failures(self, tmp_path, monkeypatch):
        """main() should produce output even when some files fail."""
        good = _make_text_file(tmp_path / "good.txt", "Partial success content.")
        bad = _make_unsupported_file(tmp_path / "bad.xyz")

        # Point output to tmp
        out_dir = tmp_path / "output"
        monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(out_dir))

        monkeypatch.setattr(
            "sys.argv",
            ["extract.py", str(good), str(bad), "--install-missing", "no"],
        )

        # Need to re-import config constants since they're evaluated at import time
        # So we patch the OUTPUT_* in utils directly
        out_text = out_dir / "full_text.txt"
        out_meta = out_dir / "metadata.json"
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", out_dir)
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", out_text)
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", out_meta)
        monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)

        main()

        assert out_text.exists(), "full_text.txt should be created"
        assert out_meta.exists(), "metadata.json should be created"
        text = out_text.read_text(encoding="utf-8")
        assert "Partial success content" in text

        meta = json.loads(out_meta.read_text(encoding="utf-8"))
        assert meta["total_sources"] == 1

    def test_extraction_error_is_not_system_exit(self):
        """ExtractionError should NOT be a subclass of SystemExit."""
        assert not issubclass(ExtractionError, SystemExit)
        with pytest.raises(ExtractionError):
            raise ExtractionError("test")


# ═══════════════════════════════════════════════════════════════════════════
#  FIX #3 — Explicit input order preservation
# ═══════════════════════════════════════════════════════════════════════════

class TestInputOrderPreservation:
    """Verify that user-given file order is preserved."""

    def test_explicit_files_preserve_order(self, tmp_path):
        """Files specified explicitly should keep the user's order."""
        f_c = _make_text_file(tmp_path / "charlie.txt", "C")
        f_a = _make_text_file(tmp_path / "alpha.txt", "A")
        f_b = _make_text_file(tmp_path / "bravo.txt", "B")

        # User passes: charlie, alpha, bravo
        result = resolve_input_files([str(f_c), str(f_a), str(f_b)])

        names = [p.name for p in result]
        assert names == ["charlie.txt", "alpha.txt", "bravo.txt"], (
            f"Expected user order, got: {names}"
        )

    def test_explicit_files_reverse_order(self, tmp_path):
        """Reverse alphabetical order should be preserved as-is."""
        f1 = _make_text_file(tmp_path / "note2.md", "two")
        f2 = _make_text_file(tmp_path / "note1.md", "one")

        result = resolve_input_files([str(f1), str(f2)])
        names = [p.name for p in result]
        assert names == ["note2.md", "note1.md"], (
            f"Expected note2 before note1, got: {names}"
        )

    def test_directory_contents_are_sorted(self, tmp_path):
        """Files from directory expansion SHOULD be sorted deterministically."""
        d = tmp_path / "books"
        d.mkdir()
        _make_text_file(d / "zebra.txt", "Z")
        _make_text_file(d / "alpha.txt", "A")
        _make_text_file(d / "middle.txt", "M")

        result = resolve_input_files([str(d)])
        names = [p.name for p in result]
        assert names == sorted(names, key=str.lower), (
            f"Directory contents should be sorted, got: {names}"
        )

    def test_mixed_explicit_and_directory(self, tmp_path):
        """Explicit file order is preserved, directory expansion is sorted within itself."""
        explicit = _make_text_file(tmp_path / "explicit_z.txt", "Z first")

        d = tmp_path / "folder"
        d.mkdir()
        _make_text_file(d / "b_in_dir.txt", "B")
        _make_text_file(d / "a_in_dir.txt", "A")

        result = resolve_input_files([str(explicit), str(d)])
        names = [p.name for p in result]
        # explicit_z should come first, then the dir contents sorted
        assert names[0] == "explicit_z.txt"
        assert names[1:] == ["a_in_dir.txt", "b_in_dir.txt"]

    def test_deduplication_preserves_first_occurrence(self, tmp_path):
        """When a file is mentioned twice, keep the FIRST position."""
        f = _make_text_file(tmp_path / "dup.txt", "dup")
        result = resolve_input_files([str(f), str(f)])
        assert len(result) == 1
        assert result[0].name == "dup.txt"


# ═══════════════════════════════════════════════════════════════════════════
#  NIT — Glob filtering by SUPPORTED_EXTENSIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestGlobFiltering:
    """Verify that glob expansion filters by supported extensions."""

    def test_glob_filters_unsupported_extensions(self, tmp_path):
        """Glob should not include files with unsupported extensions."""
        _make_text_file(tmp_path / "notes.txt", "good")
        _make_unsupported_file(tmp_path / "image.png")
        _make_unsupported_file(tmp_path / "data.csv")

        pattern = str(tmp_path / "*")
        result = resolve_input_files([pattern])

        extensions = {p.suffix.lower() for p in result}
        assert extensions <= SUPPORTED_EXTENSIONS, (
            f"Unsupported extensions found in glob results: {extensions - SUPPORTED_EXTENSIONS}"
        )
        names = [p.name for p in result]
        assert "notes.txt" in names
        assert "image.png" not in names
        assert "data.csv" not in names

    def test_glob_includes_supported_extensions(self, tmp_path):
        """Glob should include all supported file types."""
        _make_text_file(tmp_path / "readme.md", "# README")
        _make_html_file(tmp_path / "page.html")
        _make_text_file(tmp_path / "notes.txt", "notes")

        pattern = str(tmp_path / "*")
        result = resolve_input_files([pattern])

        names = {p.name for p in result}
        assert "readme.md" in names
        assert "page.html" in names
        assert "notes.txt" in names

    def test_glob_results_are_sorted(self, tmp_path):
        """Glob expansion results should be sorted deterministically."""
        _make_text_file(tmp_path / "z_file.txt", "z")
        _make_text_file(tmp_path / "a_file.txt", "a")
        _make_text_file(tmp_path / "m_file.txt", "m")

        pattern = str(tmp_path / "*.txt")
        result = resolve_input_files([pattern])
        names = [p.name for p in result]
        assert names == sorted(names, key=str.lower)


# ═══════════════════════════════════════════════════════════════════════════
#  Additional edge-case tests
# ═══════════════════════════════════════════════════════════════════════════

class TestParseArguments:
    """Basic tests for argument parsing."""

    def test_basic_parsing(self):
        paths, mode, _ = parse_arguments(
            ["extract.py", "book.pdf", "--mode", "text", "--install-missing", "no"]
        )
        assert paths == ["book.pdf"]
        assert mode == "text"

    def test_multiple_inputs(self):
        paths, mode, _ = parse_arguments(
            ["extract.py", "a.pdf", "b.epub", "c.txt"]
        )
        assert paths == ["a.pdf", "b.epub", "c.txt"]
        assert mode == "text"  # default

    def test_technical_mode(self):
        paths, mode, _ = parse_arguments(
            ["extract.py", "a.pdf", "--mode", "technical"]
        )
        assert mode == "technical"

    def test_invalid_mode_defaults_to_text(self):
        _, mode, _ = parse_arguments(
            ["extract.py", "a.pdf", "--mode", "invalid"]
        )
        assert mode == "text"


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_known_word_count(self):
        text = " ".join(["word"] * 100)
        tokens = estimate_tokens(text)
        # 100 words / 0.75 ≈ 133
        assert tokens == 133


class TestDetectStructure:
    """Tests for structure detection."""

    def test_detects_chapters(self):
        text = "Chapter 1 Introduction\nSome text.\nChapter 2 Details\nMore text."
        result = detect_structure(text)
        assert result["chapters_detected"] == 2

    def test_detects_toc(self):
        text = "Table of Contents\n1. Intro\n2. Body"
        result = detect_structure(text)
        assert result["has_toc"] is True

    def test_no_toc(self):
        text = "Just some regular text without any structure."
        result = detect_structure(text)
        assert result["has_toc"] is False

    def test_toc_chinese(self):
        assert detect_structure("目录\n第一章 开始\n第二章 进阶\n")["has_toc"] is True

    def test_toc_japanese(self):
        assert detect_structure("目次\n本文")["has_toc"] is True

    def test_toc_french(self):
        assert detect_structure("Table des matières\n1 Intro")["has_toc"] is True

    def test_toc_german(self):
        assert detect_structure("Inhaltsverzeichnis\n1 Einleitung")["has_toc"] is True

    def test_toc_italian(self):
        assert detect_structure("Indice\n1 Introduzione")["has_toc"] is True

    def test_toc_dutch(self):
        assert detect_structure("Inhoudsopgave\n1 Inleiding")["has_toc"] is True

    def test_toc_spanish_accented(self):
        assert detect_structure("Índice\n1 Introducción")["has_toc"] is True

    def test_toc_traditional_chinese(self):
        assert detect_structure("目錄\n第一章")["has_toc"] is True

    def test_toc_italian_sommario(self):
        assert detect_structure("Sommario\n1 Introduzione")["has_toc"] is True

    def test_toc_inline_word_is_not_toc(self):
        # "contents"/"index" mid-sentence must not be mistaken for a ToC header
        text = "The contents of this chapter are varied and the index is long.\n"
        assert detect_structure(text)["has_toc"] is False

    def test_numbered_list_items_are_not_chapters(self):
        # The AI-Engineering failure: numbered list items were counted as chapters.
        text = (
            "1. Compared to characters, tokens allow the model to break words into\n"
            "2. Because there are fewer unique tokens than unique words, this reduces\n"
            "3. Tokens also help the model process unknown words, for instance a word\n"
        )
        assert detect_structure(text)["chapters_detected"] == 0

    def test_inline_cross_references_are_not_chapters(self):
        text = (
            "Chapter 6 explores why context is important for a model to perform.\n"
            "As discussed, Chapter 8 are relevant beyond finetuning in this case.\n"
        )
        assert detect_structure(text)["chapters_detected"] == 0

    def test_years_are_not_chapters(self):
        text = "2025. AI is often mentioned as a competitive advantage these days.\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_real_headings_with_titles_count(self):
        text = "Chapter 1. Introduction to Building AI\nbody\nChapter 2. Understanding Models\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_portuguese_capitulo(self):
        text = "Capítulo 1\nalgum texto\nCapítulo 2\nmais texto\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_distinct_numbering_dedups_toc_and_body(self):
        # A ToC heading and the body heading for the same chapter count once.
        text = "Capítulo 1: Alicerces\n...\nCapítulo 1\nbody of chapter one\n"
        assert detect_structure(text)["chapters_detected"] == 1

    def test_roman_numeral_chapters(self):
        text = "I: Loomings\nbody\nII: The Carpet-Bag\nbody\nIII: The Spouter-Inn\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_roman_requires_title_after_separator(self):
        # bare "V." (page divider) or "I" alone is not a chapter
        assert detect_structure("V.\nI\nII\n")["chapters_detected"] == 0

    def test_roman_rejects_non_canonical(self):
        # "IIII"/"VV" are not valid roman numerals
        assert detect_structure("IIII: Bad\nVV: Also bad\n")["chapters_detected"] == 0

    def test_scans_full_text_not_just_head(self):
        # A chapter heading far past the old 50k-char window must still be found.
        text = "Capítulo 1\n" + ("filler word " * 6000) + "\nCapítulo 2\n"
        assert detect_structure(text)["chapters_detected"] == 2

    # ── Chinese (CJK) chapter headings ──────────────────────────────────────

    def test_chinese_di_n_zhang(self):
        text = "第一章 绪论\n正文。\n第二章 方法\n更多正文。\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_japanese_fullwidth_digit_chapters(self):
        # Full-width Arabic digits (U+FF10–U+FF19) in "第N章" are common in
        # Japanese typesetting and must be detected like half-width "第1章".
        text = "第１章 はじめに\n本文。\n第２章 つぎ\n本文。\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_fullwidth_multi_digit_chapter(self):
        # Multi-digit full-width numbers ("第１０章") resolve to the right int.
        text = "第１章 序\n第１０章 終\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_chinese_di_n_jiang_lecture(self):
        # lecture transcripts numbered 第N讲
        text = "第一讲\n正文\n第二讲\n正文\n第三讲\n正文\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_markdown_cjk_ordinal_heading(self):
        # "## 一 · 缘起" style, common in CJK ebooks
        text = "## 一 · 缘起\n正文\n## 二 · 主体\n正文\n## 三 · 结语\n正文\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_markdown_di_n_jiang_heading(self):
        text = "## 第一讲\n正文\n## 第二讲\n正文\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_chinese_dedups_toc_and_body(self):
        # ToC entry "第一讲..... 2" and body heading "## 第一讲" count once.
        text = "第一讲..... 2\n第二讲..... 12\n## 第一讲\n正文\n## 第二讲\n正文\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_cjk_detection_does_not_affect_latin(self):
        # A bare Arabic-numeral Markdown heading is NOT a chapter (unchanged).
        assert detect_structure("## 5 Setup\n## 6 Teardown\n")["chapters_detected"] == 0

    def test_markdown_atx_chapters(self):
        text = "# Book Title\n\n## Introduction\nbody\n\n## Getting Started\nbody\n\n## Advanced\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_markdown_all_h1_chapters(self):
        text = "# Chapter One\ntext\n# Chapter Two\ntext\n# Chapter Three\ntext\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_asciidoc_section_headings(self):
        text = "= Doc Title\n\n== First Section\nbody\n\n== Second Section\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_asciidoc_deeper_levels(self):
        # AsciiDoc levels 3-6 (=== .. ======) are also recognized.
        text = "=== Alpha\nbody\n=== Beta\nbody\n=== Gamma\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_markdown_prefixed_chapter_word(self):
        # "## Chapter 1:" is not caught by the numeric scan (line starts with '#'),
        # so the structural fallback must count it.
        text = "## Chapter 1: Intro\nbody\n## Chapter 2: Models\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_headings_inside_code_fence_are_ignored(self):
        text = "# Real A\n\n```python\n# a comment\n# another comment\n```\n\n# Real B\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_plain_prose_has_no_structural_chapters(self):
        # Regression guard: no headings -> still 0, unchanged behavior
        text = "Just paragraphs of prose.\nMore prose here.\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_numeric_chapters_win_over_markdown_subsections(self):
        # A book with real "Chapter N" headings must report the numeric count,
        # not the count of markdown subsection headings.
        text = "Chapter 1: Intro\n## sub a\n## sub b\n## sub c\nChapter 2: Next\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_chinese_numeral_parsing(self):
        assert _cn_numeral_to_int("一") == 1
        assert _cn_numeral_to_int("十") == 10
        assert _cn_numeral_to_int("十一") == 11
        assert _cn_numeral_to_int("二十") == 20
        assert _cn_numeral_to_int("二十一") == 21
        assert _cn_numeral_to_int("一百零八") == 108
        assert _cn_numeral_to_int("15") == 15
        assert _cn_numeral_to_int("１２") == 12  # full-width Arabic digits
        assert _cn_numeral_to_int("不是数字") is None
        assert _cn_numeral_to_int("9999") is None  # out of 1..999 chapter range

    def test_french_chapitre(self):
        assert detect_structure("Chapitre 1\nx\nChapitre 2\nx")["chapters_detected"] == 2

    def test_german_kapitel(self):
        assert detect_structure("Kapitel 1\nx\nKapitel 2\nx")["chapters_detected"] == 2

    def test_italian_capitolo(self):
        assert detect_structure("Capitolo 1\nx\nCapitolo 2\nx")["chapters_detected"] == 2

    def test_dutch_hoofdstuk(self):
        assert detect_structure("Hoofdstuk 1\nx\nHoofdstuk 2\nx")["chapters_detected"] == 2

    def test_german_kapitel_with_title(self):
        text = "Kapitel 1: Einführung\nx\nKapitel 2: Methoden\nx"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_european_lowercase_cross_reference_not_chapter(self):
        # A lowercase continuation is prose / a cross-reference, not a heading —
        # the existing _HEADING_TAIL guard must reject it for the new words too.
        text = "Kapitel 3 behandelt das Thema ausführlich.\nChapitre 6 explique le contexte ici.\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_german_kapitel_umlaut_title(self):
        # "Überblick" starts with Ü (U+00DC) — the widened À-Þ range accepts it.
        text = "Kapitel 1 Anfang\nx\nKapitel 2 Überblick\nx"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_roman_heading_umlaut_title(self):
        # _ROMAN_HEAD range widened too: a Roman heading with an Ü-title counts.
        text = "I: Überblick\nbody\nII: Anfang\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_setext_rst_equals_three_sections(self):
        text = ("Introduction\n============\nbody\n\n"
                "Getting Started\n===============\nbody\n\n"
                "Advanced\n========\nbody\n")
        assert detect_structure(text)["chapters_detected"] == 3

    def test_setext_rst_dash_two_sections(self):
        text = "Methods\n-------\nbody\n\nResults\n-------\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_setext_markdown_h1(self):
        text = "First\n=====\ntext\n\nSecond\n======\ntext\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_setext_equals_top_level_wins_over_dash(self):
        # "=" (level 1) is shallower than "-" (level 2); the two "=" titles win.
        text = "Chap One\n========\nSec a\n-----\nSec b\n-----\nChap Two\n========\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_setext_thematic_break_under_paragraph_not_heading(self):
        text = "This is a normal paragraph of body text.\n---\nmore text follows here too.\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_setext_horizontal_rule_with_blank_above_not_heading(self):
        text = "text here\n\n---\n\nmore\n\n***\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_setext_simple_table_border_not_heading(self):
        text = "Name    Value\n=====   =====\nfoo     1\nbar     2\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_setext_yaml_front_matter_not_heading(self):
        text = "---\ntitle: foo\nauthor: bar\n---\nbody text here\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_setext_inside_code_fence_ignored(self):
        text = "```\nTitle\n=====\nAnother\n=======\n```\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_atx_all_punctuation_title_not_heading(self):
        # "=====   =====" matches the ATX regex (group 2 = "====="), but the \w guard
        # rejects it: an all-punctuation title is not a real heading.
        text = "intro line\n=====   =====\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 0

    def test_atx_heading_followed_by_underline_not_double_counted(self):
        # A malformed mix (ATX heading then a "=" underline) must not count the
        # same heading twice (once as ATX, once as setext).
        text = "# Hi\n====\n# Bye\n=====\n"
        assert detect_structure(text)["chapters_detected"] == 2


class TestTextExtraction:
    """Tests for plain-text file extraction."""

    def test_extract_txt_file(self, tmp_path):
        txt = _make_text_file(tmp_path / "simple.txt", "Simple text content for testing.")

        with mock.patch("book_to_skill.utils.prepare_dependencies"):
            result = extract_single_file(txt, "text", "no")

        assert result["format"] == "txt"
        assert result["extraction_method"] == "plain-text"
        assert "Simple text content" in result["text"]

    def test_extract_md_file(self, tmp_path):
        md = _make_md_file(tmp_path / "notes.md", "# My Notes\n\nSome notes here.")

        with mock.patch("book_to_skill.utils.prepare_dependencies"):
            result = extract_single_file(md, "text", "no")

        assert result["format"] == "md"
        assert "My Notes" in result["text"]


class TestHtmlExtraction:
    """Tests for HTML file extraction."""

    def test_extract_html_file(self, tmp_path):
        html_file = _make_html_file(tmp_path / "page.html")

        with mock.patch("book_to_skill.utils.prepare_dependencies"):
            result = extract_single_file(html_file, "text", "no")

        assert result["format"] == "html"
        assert result["extraction_method"] == "html-parser"
        assert "Test paragraph" in result["text"]


class TestDocxExtraction:
    """Tests for DOCX extraction via the zipfile fallback."""

    def test_extract_docx_zipfile_fallback(self, tmp_path):
        docx = _make_minimal_docx(tmp_path / "test.docx")

        with mock.patch("book_to_skill.utils.prepare_dependencies"):
            result = extract_single_file(docx, "text", "no")

        assert result["format"] == "docx"
        assert "DOCX test paragraph" in result["text"]

    def test_extract_docx_xxe_rejection(self, tmp_path):
        """Verify that a DOCX with malicious DTD or entity declarations is rejected."""
        from book_to_skill.parsers.docx import extract_docx
        
        # Create a malicious DOCX
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        xml = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <!DOCTYPE w:document [
              <!ENTITY xxe SYSTEM "file:///etc/passwd">
            ]>
            <w:document xmlns:w="{ns}">
              <w:body>
                <w:p><w:r><w:t>&xxe;</w:t></w:r></w:p>
              </w:body>
            </w:document>
        """)
        bad_docx = tmp_path / "malicious.docx"
        with zipfile.ZipFile(bad_docx, "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            
        with pytest.raises(ExtractionError, match="Security validation failed"):
            extract_docx(str(bad_docx))



class TestResolveInputFiles:
    """Additional edge-case tests for resolve_input_files."""

    def test_nonexistent_file_kept_for_error_reporting(self, tmp_path):
        """A nonexistent explicit path is kept so extract_single_file can report it."""
        fake = tmp_path / "nonexistent.pdf"
        result = resolve_input_files([str(fake)])
        assert len(result) == 1
        assert result[0].name == "nonexistent.pdf"

    def test_empty_directory_returns_empty(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        result = resolve_input_files([str(d)])
        assert result == []

    def test_directory_only_picks_supported(self, tmp_path):
        d = tmp_path / "mixed"
        d.mkdir()
        _make_text_file(d / "readme.txt", "hi")
        _make_unsupported_file(d / "photo.jpg")

        result = resolve_input_files([str(d)])
        names = [p.name for p in result]
        assert "readme.txt" in names
        assert "photo.jpg" not in names


class TestDependencyCheck:
    """Tests for the --check preflight (run_dependency_check)."""

    def test_all_present_reports_ready(self, capsys):
        from book_to_skill.dependencies import run_dependency_check

        with mock.patch("book_to_skill.dependencies.python_module_available", return_value=True), \
             mock.patch("book_to_skill.dependencies.shutil.which", return_value="/usr/bin/tool"):
            code = run_dependency_check()

        out = capsys.readouterr().out
        assert code == 0
        assert "All optional dependencies are installed" in out
        assert "✗" not in out

    def test_all_missing_lists_install_commands(self, capsys):
        from book_to_skill.dependencies import run_dependency_check

        with mock.patch("book_to_skill.dependencies.python_module_available", return_value=False), \
             mock.patch("book_to_skill.dependencies.shutil.which", return_value=None):
            code = run_dependency_check()

        out = capsys.readouterr().out
        assert code == 0
        # consolidated pip command lists the missing python packages
        assert "pip install" in out
        assert "docling" in out and "striprtf" in out
        # MOBI has no fallback → flagged as required
        assert "MISSING — required, no fallback" in out
        # Calibre hint is surfaced as a system dependency
        assert "calibre-ebook.com" in out

    def test_pdftotext_alone_satisfies_pdf_text(self, capsys):
        """pdftotext present (system) should mark PDF text-heavy ready even with no python PDF libs."""
        from book_to_skill.dependencies import run_dependency_check

        def which(cmd):
            return "/usr/bin/pdftotext" if cmd == "pdftotext" else None

        with mock.patch("book_to_skill.dependencies.python_module_available", return_value=False), \
             mock.patch("book_to_skill.dependencies.shutil.which", side_effect=which):
            run_dependency_check()

        out = capsys.readouterr().out
        # the PDF (text-heavy) group line should be followed by a "ready" status
        pdf_block = out.split("PDF (text-heavy)", 1)[1].split("PDF (technical", 1)[0]
        assert "ready" in pdf_block


# ---------------------------------------------------------------------------
# Parser exception logging
# ---------------------------------------------------------------------------

class TestParserExceptionLogging:
    """Verify unexpected parser exceptions surface on stderr, chain returns None."""

    def test_pypdf_warns_on_unexpected_error_and_returns_none(self, tmp_path, capsys):
        """Monkeypatch pypdf import to raise; confirm None + stderr warning."""
        from book_to_skill.parsers.pdf import extract_with_pypdf

        broken = tmp_path / "broken.pdf"
        broken.write_bytes(b"%PDF-1.4 fake")

        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "pypdf":
                raise RuntimeError("simulated failure")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            result = extract_with_pypdf(str(broken))

        assert result is None
        captured = capsys.readouterr()
        assert "[warn]" in captured.err
        assert "failed:" in captured.err


class TestRtfUnicodeFallback:
    """The dependency-free RTF fallback decodes RTF \\uN unicode escapes."""

    _BS = chr(92)  # a single backslash, never written as a literal \-escape

    def _esc(self, codepoint, fallback="?"):
        # Build the RTF escape: backslash + "u" + number + one fallback char.
        return self._BS + "u" + str(codepoint) + fallback

    def test_rtf_unicode_right_single_quote(self):
        assert strip_rtf_fallback("It" + self._esc(8217) + "s") == "It’s"

    def test_rtf_unicode_em_dash(self):
        assert strip_rtf_fallback("a " + self._esc(8212) + " b") == "a — b"

    def test_rtf_unicode_accented_letter(self):
        assert strip_rtf_fallback("caf" + self._esc(233)) == "caf\xe9"

    def test_rtf_unicode_hex_fallback_consumed(self):
        # The \uN escape's fallback here is a "\'92" hex byte — it is consumed.
        text = "x" + self._BS + "u8217" + self._BS + "'92y"
        assert strip_rtf_fallback(text) == "x’y"

    def test_rtf_unicode_space_delimited_fallback(self):
        text = "x" + self._BS + "u8217 ?y"
        assert strip_rtf_fallback(text) == "x’y"

    def test_rtf_unicode_negative_codepoint(self):
        # RTF encodes code points > 32767 as negative 16-bit; -3 -> U+FFFD.
        assert strip_rtf_fallback(self._esc(-3)) == "�"

    def test_rtf_fallback_without_unicode_unchanged(self):
        # Regression: control-word-only input is unaffected by the new step.
        assert strip_rtf_fallback(self._BS + "b0 Bold" + self._BS + "b0 off") == "Boldoff"
        assert strip_rtf_fallback("{" + self._BS + "rtf1 hi}") == "hi"

    def test_rtf_unicode_consecutive_escapes_with_hex_fallback(self):
        # Two adjacent \uN escapes, each with a \'XX hex fallback, decode cleanly.
        text = self._BS + "u8220" + self._BS + "'93Hi" + self._BS + "u8221" + self._BS + "'94"
        assert strip_rtf_fallback(text) == "“Hi”"


class TestHtmlEntityDecoding:
    """The stdlib HTML parser decodes entities exactly once (not twice)."""

    def _text(self, fragment):
        # Feed a raw fragment (no block tags) through a fresh stdlib parser.
        from book_to_skill.parsers.html import _HTMLTextExtractor
        p = _HTMLTextExtractor()
        p.feed(fragment)
        return p.get_text()

    def test_double_encoded_ampersand(self):
        # The bug: this used to collapse to "&" (decoded twice).
        assert self._text("&amp;amp;") == "&amp;"

    def test_double_encoded_tag(self):
        assert self._text("&amp;lt;tag&amp;gt;") == "&lt;tag&gt;"

    def test_single_entities_still_decode(self):
        assert self._text("&lt;b&gt;") == "<b>"
        assert self._text("&amp;") == "&"

    def test_numeric_and_named_entities(self):
        assert self._text("&#233;") == "é"      # decimal numeric
        assert self._text("&#xE9;") == "é"      # hex numeric
        assert self._text("&copy;") == "©"      # non-ASCII named entity
        assert self._text("hello") == "hello"   # plain text

    def test_skip_tag_content_excluded(self):
        # Confirms the change didn't disturb skip-tag handling.
        assert self._text("<style>x{}</style>keep") == "keep"


class TestDocxTableReconstruction:
    """The stdlib DOCX fallback tab-joins table rows and preserves order."""

    _NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def _make_docx(self, tmp_path, body_xml):
        import zipfile
        p = tmp_path / "t.docx"
        doc = (
            '<?xml version="1.0"?>'
            f'<w:document xmlns:w="{self._NS}"><w:body>{body_xml}</w:body></w:document>'
        )
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("word/document.xml", doc)
        return str(p)

    def _para(self, text):
        return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"

    def _cell(self, text):
        return f"<w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"

    def test_table_rows_are_tab_joined(self, tmp_path):
        body = (
            self._para("Intro")
            + "<w:tbl><w:tr>" + self._cell("Name") + self._cell("Value") + "</w:tr>"
            + "<w:tr>" + self._cell("foo") + self._cell("1") + "</w:tr></w:tbl>"
        )
        out = extract_docx_with_zipfile(self._make_docx(tmp_path, body))
        assert "Name\tValue" in out
        assert "foo\t1" in out

    def test_document_order_preserved(self, tmp_path):
        body = (
            self._para("Before")
            + "<w:tbl><w:tr>" + self._cell("R1C1") + self._cell("R1C2") + "</w:tr></w:tbl>"
            + self._para("After")
        )
        out = extract_docx_with_zipfile(self._make_docx(tmp_path, body))
        assert out.index("Before") < out.index("R1C1") < out.index("After")

    def test_paragraph_only_document_unchanged(self, tmp_path):
        body = self._para("Just a paragraph") + self._para("And another")
        out = extract_docx_with_zipfile(self._make_docx(tmp_path, body))
        assert out == "Just a paragraph\nAnd another"

    def test_empty_cell_still_tab_joined(self, tmp_path):
        body = (
            "<w:tbl><w:tr>" + self._cell("A")
            + "<w:tc><w:p></w:p></w:tc></w:tr></w:tbl>"
        )
        out = extract_docx_with_zipfile(self._make_docx(tmp_path, body))
        # "\t".join(["A", ""]) -> "A\t"; the empty cell becomes an empty field.
        assert out == "A\t"

    def test_sdt_wrapped_content_is_preserved(self, tmp_path):
        # Word wraps TOC/cover-page/form content in <w:sdt> content controls,
        # which are direct children of <w:body> but not <w:p>/<w:tbl>. The
        # recursive walk must still find paragraphs/tables inside them.
        body = (
            self._para("Before")
            + "<w:sdt><w:sdtContent>" + self._para("Inside SDT") + "</w:sdtContent></w:sdt>"
            + self._para("After")
        )
        out = extract_docx_with_zipfile(self._make_docx(tmp_path, body))
        assert out == "Before\nInside SDT\nAfter"
