"""
Test suite for the three PR blocker fixes + nits in the extractor package.

Covers:
  Fix #1 — EPUB extraction tuple-unpack regression
  Fix #2 — Batch resilience (ExtractionError instead of sys.exit)
  Fix #3 — Explicit input order preservation
  Nit   — Glob results filtered by SUPPORTED_EXTENSIONS
"""

import json
import os
import sys
import textwrap
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: make sure the extractor package is importable
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from extractor.exceptions import ExtractionError
from extractor.utils import (
    resolve_input_files,
    extract_single_file,
    parse_arguments,
    estimate_tokens,
    detect_structure,
    main,
)
from extractor.config import SUPPORTED_EXTENSIONS


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
        from extractor.parsers.epub import extract_with_ebooklib

        # With ebooklib likely not installed in test env → returns None
        result = extract_with_ebooklib("nonexistent.epub")
        assert result is None or isinstance(result, str), (
            f"extract_with_ebooklib should return str|None, got {type(result)}"
        )

    def test_epub_extraction_via_zipfile_fallback(self, tmp_path):
        """EPUB with zipfile fallback should work end-to-end."""
        epub_path = _make_minimal_epub(tmp_path / "test.epub")

        # Mock prepare_dependencies to be a no-op
        with mock.patch("extractor.utils.prepare_dependencies"):
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
        with mock.patch("extractor.utils.prepare_dependencies"):
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
        from extractor.parsers.epub import extract_with_zipfile

        epub_path = _make_oebps_epub(tmp_path / "oebps.epub")
        text = extract_with_zipfile(str(epub_path))

        assert text is not None, "extract_with_zipfile returned None for OEBPS EPUB"
        assert "Chapter one from OEBPS" in text
        assert "Chapter two from OEBPS" in text

    def test_full_extraction_with_oebps_epub(self, tmp_path):
        """End-to-end: extract_single_file should succeed with OEBPS layout."""
        epub_path = _make_oebps_epub(tmp_path / "test_oebps.epub")

        with mock.patch("extractor.utils.prepare_dependencies"):
            result = extract_single_file(epub_path, "text", "no")

        assert result["format"] == "epub"
        assert result["extraction_method"] in ("ebooklib", "zipfile")
        assert "Chapter one from OEBPS" in result["text"]
        assert "Chapter two from OEBPS" in result["text"]

    def test_container_xml_locates_opf(self, tmp_path):
        """_find_opf_path should prefer META-INF/container.xml over globbing."""
        from extractor.parsers.epub import _find_opf_path

        epub_path = _make_oebps_epub(tmp_path / "container.epub")
        with zipfile.ZipFile(epub_path) as zf:
            opf_path = _find_opf_path(zf)

        assert opf_path == "OEBPS/content.opf"

    def test_count_chapters_with_oebps(self, tmp_path):
        """count_epub_chapters should work with OPF in subdirectory."""
        from extractor.parsers.epub import count_epub_chapters

        epub_path = _make_oebps_epub(tmp_path / "chapters.epub")
        count = count_epub_chapters(str(epub_path))
        assert count == 2

    def test_root_level_opf_still_works(self, tmp_path):
        """Regression check: root-level OPF (no subdirectory) should still work."""
        from extractor.parsers.epub import extract_with_zipfile

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
                with mock.patch("extractor.utils.prepare_dependencies"):
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
        monkeypatch.setattr("extractor.utils.prepare_dependencies", lambda *a: None)

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
        monkeypatch.setattr("extractor.utils.OUTPUT_DIR", out_dir)
        monkeypatch.setattr("extractor.utils.OUTPUT_TEXT", out_text)
        monkeypatch.setattr("extractor.utils.OUTPUT_META", out_meta)
        monkeypatch.setattr("extractor.utils.prepare_dependencies", lambda *a: None)

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


class TestTextExtraction:
    """Tests for plain-text file extraction."""

    def test_extract_txt_file(self, tmp_path):
        txt = _make_text_file(tmp_path / "simple.txt", "Simple text content for testing.")

        with mock.patch("extractor.utils.prepare_dependencies"):
            result = extract_single_file(txt, "text", "no")

        assert result["format"] == "txt"
        assert result["extraction_method"] == "plain-text"
        assert "Simple text content" in result["text"]

    def test_extract_md_file(self, tmp_path):
        md = _make_md_file(tmp_path / "notes.md", "# My Notes\n\nSome notes here.")

        with mock.patch("extractor.utils.prepare_dependencies"):
            result = extract_single_file(md, "text", "no")

        assert result["format"] == "md"
        assert "My Notes" in result["text"]


class TestHtmlExtraction:
    """Tests for HTML file extraction."""

    def test_extract_html_file(self, tmp_path):
        html_file = _make_html_file(tmp_path / "page.html")

        with mock.patch("extractor.utils.prepare_dependencies"):
            result = extract_single_file(html_file, "text", "no")

        assert result["format"] == "html"
        assert result["extraction_method"] == "html-parser"
        assert "Test paragraph" in result["text"]


class TestDocxExtraction:
    """Tests for DOCX extraction via the zipfile fallback."""

    def test_extract_docx_zipfile_fallback(self, tmp_path):
        docx = _make_minimal_docx(tmp_path / "test.docx")

        with mock.patch("extractor.utils.prepare_dependencies"):
            result = extract_single_file(docx, "text", "no")

        assert result["format"] == "docx"
        assert "DOCX test paragraph" in result["text"]


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
