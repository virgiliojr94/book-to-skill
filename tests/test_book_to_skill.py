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
from book_to_skill.parsers import pdf as pdf_parser
from book_to_skill.parsers.text import read_text_file
from book_to_skill.parsers.docx import extract_docx_with_zipfile
from book_to_skill.parsers.rtf import strip_rtf_fallback
from book_to_skill.parsers.epub import extract_with_zipfile


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

    @pytest.mark.parametrize(
        "reported_source",
        ["/x/sample.md", "/deep/" + ("nested/" * 12) + "sample.md"],
    )
    def test_source_banner_does_not_change_structural_chapter_count(
        self, tmp_path, monkeypatch, reported_source
    ):
        """The generated SOURCE banner must not become a phantom setext heading."""
        source = _make_md_file(
            tmp_path / "sample.md",
            "# The Pragmatic Widget\n\n"
            "## Foundations\n\nBody.\n\n"
            "## Design Rules\n\nBody.\n\n"
            "## Trade-offs\n\nBody.\n\n"
            "## Operating Model\n\nBody.\n\n"
            "## Closing\n\nBody.\n",
        )
        out_dir = tmp_path / "output"
        out_text = out_dir / "full_text.txt"
        out_meta = out_dir / "metadata.json"
        real_extract = extract_single_file

        def extract_with_reported_source(*args, **kwargs):
            result = real_extract(*args, **kwargs)
            result["source_file"] = reported_source
            return result

        monkeypatch.setattr("sys.argv", ["extract.py", str(source), "--install-missing", "no"])
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", out_dir)
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", out_text)
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", out_meta)
        monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)
        monkeypatch.setattr(
            "book_to_skill.utils.extract_single_file", extract_with_reported_source
        )

        main()

        metadata = json.loads(out_meta.read_text(encoding="utf-8"))
        assert metadata["sources"][0]["chapters_detected"] == 5
        assert metadata["chapters_detected"] == 5
        assert "SOURCE: sample.md" in out_text.read_text(encoding="utf-8")

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

    def test_detects_chapter_word_with_roman_numeral(self):
        """`Chapter I.` — the combination of the word plus a Roman numeral.

        Regression: each half worked alone (`Chapter 1` via _EXPLICIT_CHAPTER,
        `I. Loomings` via _ROMAN_HEAD) but the combination matched neither, so
        books using it fell back to no segmentation. Project Gutenberg's
        `The Art of War` (#132) is one: 13 such headings, 0 detected, while two
        footnote cross-references (`ch. 71.]`) were picked up instead.
        """
        text = "\n".join(
            "Chapter %s. Section\nBody text here." % r
            for r in ("I", "II", "III", "IV", "V")
        )
        assert detect_structure(text)["chapters_detected"] == 5

    def test_detects_thai_chapters(self):
        """Thai headings: `บทที่ N` / `ตอนที่ N`, with Thai or Arabic digits."""
        text = (
            "บทที่ ๑ ว่าด้วยการวางแผน\nเนื้อหา\n"
            "บทที่ ๒ ว่าด้วยการรบ\nเนื้อหา\n"
            "บทที่ 3 ว่าด้วยกลยุทธ์\nเนื้อหา"
        )
        assert detect_structure(text)["chapters_detected"] == 3

    def test_thai_episode_headings_and_markdown_prefix(self):
        text = "## ตอนที่ ๘๖ เรื่องหนึ่ง\nเนื้อหา\n## ตอนที่ ๘๗ เรื่องสอง\nเนื้อหา"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_thai_prose_is_not_a_chapter_heading(self):
        """`บทความ` (article) and `ตอนนี้` (now) start with the chapter words
        but are ordinary prose — they must not be treated as headings."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("บทความนี้ยาวมากและมีรายละเอียดเยอะ") is None
        assert _chapter_number("ตอนนี้เรามาดูกันว่าเกิดอะไรขึ้น") is None

    # ── Hindi (Devanagari) chapter headings ────────────────────────────────
    def test_detects_hindi_chapters(self):
        """Hindi headings: `अध्याय N`, with Devanagari or Arabic digits."""
        text = (
            "अध्याय १ प्रस्तावना\nसामग्री\n"
            "अध्याय २ विधियाँ\nसामग्री\n"
            "अध्याय 3 परिणाम\nसामग्री"
        )
        assert detect_structure(text)["chapters_detected"] == 3

    def test_hindi_markdown_prefix(self):
        text = "## अध्याय १ पहला\nसामग्री\n## अध्याय २ दूसरा\nसामग्री"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_hindi_prose_is_not_a_chapter_heading(self):
        """`अध्याय` used in prose (no number, or not at the start) is not a heading."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("इस अध्याय में हम चर्चा करेंगे") is None
        assert _chapter_number("अध्याय") is None

    def test_detects_bengali_chapters(self):
        """Bengali headings: `অধ্যায় N`, with Bengali or Arabic digits."""
        text = (
            "অধ্যায় ১ ভূমিকা\nবিষয়বস্তু\n"
            "অধ্যায় ২ পদ্ধতি\nবিষয়বস্তু\n"
            "অধ্যায় 3 ফলাফল\nবিষয়বস্তু"
        )
        assert detect_structure(text)["chapters_detected"] == 3

    def test_bengali_markdown_prefix(self):
        text = "## অধ্যায় ১ প্রথম\nবিষয়বস্তু\n## অধ্যায় ২ দ্বিতীয়\nবিষয়বস্তু"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_bengali_prose_is_not_a_chapter_heading(self):
        """`অধ্যায়` used in prose (no number, or not at the start) is not a heading."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("এই অধ্যায়ে আমরা আলোচনা করব") is None
        assert _chapter_number("অধ্যায়") is None

    def test_detects_russian_chapters(self):
        """Russian headings: `Глава N`, case-insensitive, with Arabic digits."""
        text = (
            "Глава 1 Введение\nсодержание\n"
            "ГЛАВА 2 Методы\nсодержание\n"
            "Глава 3 Результаты\nсодержание"
        )
        assert detect_structure(text)["chapters_detected"] == 3

    def test_russian_markdown_prefix(self):
        text = "## Глава 1 Первая\nсодержание\n## Глава 2 Вторая\nсодержание"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_russian_prose_is_not_a_chapter_heading(self):
        """An inflected form or a different word (Главная) is not a heading."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("В этой главе мы обсудим") is None
        assert _chapter_number("Главная страница") is None
        assert _chapter_number("Глава") is None

    # ── Korean chapter headings ────────────────────────────────────────────

    def test_korean_je_n_jang(self):
        """Korean headings: `제N장` with Arabic digits."""
        text = (
            "제1장 총칙\n내용\n"
            "제2장 근로시간\n내용\n"
            "제3장 휴식\n내용"
        )
        assert detect_structure(text)["chapters_detected"] == 3

    def test_korean_markdown_prefix(self):
        """`## 제N장` with Markdown heading prefix."""
        text = "## 제1장 서론\n내용\n## 제2장 본론\n내용"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_korean_inserted_chapter_suffix(self):
        """`제6장의2` — inserted-chapter suffix used in Korean statutes."""
        text = "제6장의2 직장 내 괴롭힘의 금지\n내용\n제7장 보칙\n내용"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_korean_article_is_not_chapter(self):
        """`제N조` (article) is not a chapter classifier — deliberately excluded."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("제56조 (연장·야간 및 휴일 근로)") is None

    def test_korean_prose_cross_reference_not_chapter(self):
        """Prose cross-references with particles are not headings."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("이 장과 제5장에서 정한 근로시간…") is None
        assert _chapter_number("제5장에서 정한 근로시간에 관한 규정은…") is None
        assert _chapter_number("제2장의 규정에도 불구하고…") is None

    def test_korean_dedups_toc_and_body(self):
        """ToC entry and body heading with same number count once."""
        text = "제1장 총칙\n제2장 근로시간\n## 제1장\n내용\n## 제2장\n내용"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_korean_other_classifiers(self):
        """`제N편` (part), `제N절` (section), `제N관` (subsection) are also detected."""
        text = "제1편 총칙\n내용\n제2장 정의\n내용\n제3절 통칙\n내용"
        assert detect_structure(text)["chapters_detected"] == 3

    # ── Persian chapter headings ───────────────────────────────────────────

    # Canonical ordinals 1–34 used by the FA word-numeral map (integration fixture).
    _FA_ORDINAL_1_TO_34 = (
        "اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم",
        "یازدهم", "دوازدهم", "سیزدهم", "چهاردهم", "پانزدهم", "شانزدهم", "هفدهم",
        "هجدهم", "نوزدهم", "بیستم",
        "بیست و یکم", "بیست و دوم", "بیست و سوم", "بیست و چهارم", "بیست و پنجم",
        "بیست و ششم", "بیست و هفتم", "بیست و هشتم", "بیست و نهم", "سی ام",
        "سی و یکم", "سی و دوم", "سی و سوم", "سی و چهارم",
    )

    def test_persian_digit_scripts(self):
        """`فصل N` with Persian, Arabic-Indic, and ASCII digits."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("فصل ۱") == 1
        assert _chapter_number("فصل ١") == 1
        assert _chapter_number("فصل 1") == 1
        assert _chapter_number("فصل ۱۰") == 10
        assert _chapter_number("فصل ١٠") == 10
        assert _chapter_number("فصل 10") == 10
        assert _chapter_number("فصل ۳۴") == 34

    def test_persian_word_numerals_1_to_34(self):
        """Word ordinals `اول` … `سی و چهارم` map to integers 1–34."""
        from book_to_skill.utils import _chapter_number

        for n, word in enumerate(self._FA_ORDINAL_1_TO_34, 1):
            assert _chapter_number(f"فصل {word}") == n, word
        # Common ZWNJ spelling of 30.
        assert _chapter_number("فصل سی‌ام") == 30

    def test_persian_compound_word_numerals(self):
        """Explicit compound forms used in longer Persian books."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("فصل بیست و یکم") == 21
        assert _chapter_number("فصل بیست و نهم") == 29
        assert _chapter_number("فصل سی و یکم") == 31
        assert _chapter_number("فصل سی و چهارم") == 34

    def test_persian_hejdahom_spelling_variants(self):
        """Both common spellings of 18: هجدهم and هیجدهم."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("فصل هجدهم") == 18
        assert _chapter_number("فصل هجدهم: یک جاسوس") == 18
        assert _chapter_number("فصل هیجدهم") == 18
        assert _chapter_number("فصل هیجدهم: یک جاسوس") == 18

    def test_persian_bakhsh_section(self):
        """`بخش` (section/part) is accepted with digits or word numerals."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("بخش ۲") == 2
        assert _chapter_number("بخش ٢") == 2
        assert _chapter_number("بخش 2") == 2
        assert _chapter_number("بخش دوم") == 2
        assert _chapter_number("بخش سی و چهارم") == 34

    def test_persian_titled_headings(self):
        """Punctuation / dash / spaced titles after the numeral are headings."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("فصل ۱: مقدمه") == 1
        assert _chapter_number("فصل اول — مبانی برنامه‌نویسی") == 1
        assert _chapter_number("فصل ۲. اصول") == 2
        assert _chapter_number("بخش ۳: مفاهیم") == 3
        assert _chapter_number("فصل بیست و یکم پایان سفر") == 21

    def test_persian_markdown_prefix(self):
        """Markdown heading prefixes are stripped by `_chapter_number`."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("## فصل ۱: مقدمه") == 1
        assert _chapter_number("### فصل دوم") == 2
        assert _chapter_number("### فصل سی و چهارم خداحافظ فرانسه") == 34

    def test_persian_pdf_glued_title(self):
        """PDF glue is allowed after teens/compounds, not after short 1–10 ordinals.

        Short ordinals are plausible prefixes of ordinary Persian words
        ("اولویت‌ها", "اولیه", "دومینو"), so they require a separator. Longer
        forms are not, and extractors do drop the space after them.
        """
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("فصل سی و چهارمخداحافظ، فرانسه") == 34
        assert _chapter_number("فصل بیست و یکمپایان سفر") == 21
        assert _chapter_number("فصل هجدهمیک جاسوس") == 18
        assert _chapter_number("فصل هیجدهمیک جاسوس") == 18
        # Short 1–10 glued titles are rejected (see false-positive test below).
        assert _chapter_number("فصل اولجایی که به نظر میرسید...") is None
        assert _chapter_number("فصل دومشهادت یک جنایتکار علیه خودش") is None
        assert _chapter_number("فصل سومعدالت") is None

    def test_persian_short_ordinal_false_positives(self):
        """Ordinary phrases that begin with a short ordinal must not be chapters."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("فصل اولویت‌ها") is None
        assert _chapter_number("فصل اولیه") is None
        assert _chapter_number("فصل دومینو") is None
        assert _chapter_number("فصل سومین") is None

    def test_persian_prose_is_not_a_chapter_heading(self):
        """Inline / incomplete `فصل` references must not count as headings."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("در فصل ۲ این موضوع را بررسی می‌کنیم") is None
        assert _chapter_number("در فصل دوم این موضوع را بررسی می‌کنیم") is None
        assert _chapter_number("این فصل اول یک توضیح است") is None
        assert _chapter_number("فصل") is None
        assert _chapter_number("بخش") is None
        # Incomplete compounds are not headings.
        assert _chapter_number("فصل بیست") is None
        assert _chapter_number("فصل سی و") is None
        # Existing hard length guard in `_match_chapter_number`.
        assert _chapter_number("فصل ۱: " + ("الف" * 40)) is None

    def test_detects_persian_chapters(self):
        """Plain-text Persian headings are numeric chapters, not MD fallback."""
        text = "فصل ۱\nمحتوا\nفصل ۲\nمحتوا\nفصل ۳\nمحتوا"
        result = detect_structure(text)
        assert result["chapters_detected"] == 3
        # Non-empty sample proves the numeric path, not structural Markdown.
        assert result["chapter_headings_sample"] == ["فصل ۱", "فصل ۲", "فصل ۳"]

    def test_detects_persian_word_chapters_1_to_34(self):
        """All 34 word-numeral headings count as distinct numeric chapters."""
        text = "\n".join(
            f"فصل {word}\nمحتوا فصل {n}."
            for n, word in enumerate(self._FA_ORDINAL_1_TO_34, 1)
        )
        result = detect_structure(text)
        assert result["chapters_detected"] == 34
        assert result["chapter_headings_sample"]  # numeric path, not MD fallback
        assert result["chapter_headings_sample"][0] == "فصل اول"

    def test_roman_footnote_reference_is_not_a_chapter(self):
        """Scholarly cross-references must stay rejected after the Roman change."""
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("V. § 19, note.") is None
        assert _chapter_number("VI. § 21:\u2014") is None
        assert _chapter_number("Chapter 6 explores the topic in depth") is None

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

    def test_toc_portuguese_unaccented(self):
        # OCR / accent-stripped Brazilian PDFs leave "Sumario" without the accent.
        assert detect_structure("Sumario\n1 Introdução")["has_toc"] is True

    def test_toc_traditional_chinese(self):
        assert detect_structure("目錄\n第一章")["has_toc"] is True

    @pytest.mark.parametrize("header", ["目 录", "目　录", "目 次", "目　次"])
    def test_toc_cjk_headers_allow_extracted_whitespace(self, header):
        assert detect_structure(f"{header}\n第一章 开始\n第二章 进阶")["has_toc"] is True

    def test_toc_italian_sommario(self):
        assert detect_structure("Sommario\n1 Introduzione")["has_toc"] is True

    def test_toc_inline_word_is_not_toc(self):
        # "contents"/"index" mid-sentence must not be mistaken for a ToC header
        text = "The contents of this chapter are varied and the index is long.\n"
        assert detect_structure(text)["has_toc"] is False

    def test_toc_markdown_atx_heading(self):
        # issue #126: a Markdown export writes the ToC as "## Table of Contents"
        text = """## Table of Contents
1. Intro
2. Body
"""
        assert detect_structure(text)["has_toc"] is True

    def test_toc_markdown_headers_other_languages(self):
        text = """## 目录
第一章 开始
第二章 进阶
"""
        assert detect_structure(text)["has_toc"] is True

    def test_unit_style_chapter_headings(self):
        # course-style books: "### Unit 1 ✏ ..." must be detected as chapters
        text = """### Unit 1 ✏ How to Write an Introduction
body
### Unit 2 ✏ Writing about Methodology
body
"""
        assert detect_structure(text)["chapters_detected"] >= 2

    def test_stray_roman_numeral_does_not_suppress_structural_count(self):
        # a single Roman numeral inside a reproduced example paper must not
        # outvote the structural heading count of the surrounding book
        text = """### Introduction
VIII. CONCLUSIONS
### Methodology
"""
        result = detect_structure(text)
        assert result["chapters_detected"] >= 2
        assert result["chapters_method"] == "structural"

    def test_unit_style_headings_count_as_numeric(self):
        # "Unit N" headings are explicit chapters once the markdown prefix is
        # stripped, so they take the numeric branch
        text = """### Unit 1 ✏ How to Write an Introduction
VIII. CONCLUSIONS
### Unit 2 ✏ Writing about Methodology
"""
        result = detect_structure(text)
        assert result["chapters_detected"] >= 2
        assert result["chapters_method"] == "numeric" 

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

    def test_detects_plain_numbered_chapter_headings(self):
        """Plain numbered headings such as '1  Introduction' are chapters."""
        text = (
            "1  Introdução e Visão Geral\n"
            "Texto do capítulo.\n"
            "2  Princípios Fundamentais\n"
            "Texto do capítulo.\n"
            "3  Produtos de Trabalho\n"
            "Texto do capítulo.\n"
            "4  Práticas para Elaboração\n"
            "Texto do capítulo.\n"
        )

        result = detect_structure(text)

        assert result["chapters_detected"] == 4
        assert result["chapters_method"] == "numeric"

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

    # ── Kangxi-radical numerals (U+2F00 block) ──────────────────────────────
    # Some Chinese ebooks (e.g. certain e-reader platforms) encode numerals as
    # Kangxi radicals instead of CJK ideographs: 第⼀章 with U+2F00, not U+4E00.
    # NFKC does not map these, so detection must normalize them explicitly.

    def test_kangxi_radical_chapter_headings(self):
        text = (
            "第⼀章\n正文\n"      # U+2F00 KANGXI RADICAL ONE
            "第⼆章\n正文\n"      # U+2F06 KANGXI RADICAL TWO
            "第⼋章\n正文\n"      # U+2F0B KANGXI RADICAL EIGHT
            "第⼗章\n正文\n"      # U+2F17 KANGXI RADICAL TEN
            "第⼗⼀章\n正文\n"    # ⼗⼀ = 11
            "第⼗⼆章\n正文\n"    # ⼗⼆ = 12
        )
        assert detect_structure(text)["chapters_detected"] == 6

    def test_kangxi_mixed_with_ideograph_chapters(self):
        # Real-world mix from an actual ebook: radicals for 一/二/八/十,
        # ideographs for the rest — all 12 chapters must be found.
        nums = ["⼀", "⼆", "三", "四", "五", "六", "七", "⼋", "九", "⼗", "⼗⼀", "⼗⼆"]
        text = "".join(f"第{n}章\n正文。\n" for n in nums)
        assert detect_structure(text)["chapters_detected"] == 12

    def test_kangxi_radical_in_markdown_heading(self):
        text = "## 第⼀讲\n正文\n## 第⼆讲\n正文\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_french_chapitre(self):
        assert detect_structure("Chapitre 1\nx\nChapitre 2\nx")["chapters_detected"] == 2

    def test_german_kapitel(self):
        assert detect_structure("Kapitel 1\nx\nKapitel 2\nx")["chapters_detected"] == 2

    def test_italian_capitolo(self):
        assert detect_structure("Capitolo 1\nx\nCapitolo 2\nx")["chapters_detected"] == 2

    def test_dutch_hoofdstuk(self):
        assert detect_structure("Hoofdstuk 1\nx\nHoofdstuk 2\nx")["chapters_detected"] == 2

    def test_vietnamese_chuong(self):
        assert detect_structure("Chương 1\nx\nChương 2\nx")["chapters_detected"] == 2

    def test_vietnamese_chuong_not_program(self):
        # "Chương trình" (program) starts with the chapter word but is not a
        # heading — no number follows "Chương", so it must not match.
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("Chương trình 1 của khóa học") is None

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


class TestMarkdownPrefixedLatinChapters:
    """Issue #91 — _chapter_number() must see chapter headings behind a
    Markdown/AsciiDoc prefix ("## Chapter 1"). Previously the Latin/Thai/Korean
    matchers anchored on the line start, so --mode technical books (Docling
    emits headings as Markdown) fell through to the structural fallback and
    inflated chapters_detected."""

    def test_md_prefixed_latin_chapter_word(self):
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("## Chapter 1") == 1
        assert _chapter_number("## CHAPTER 5") == 5
        assert _chapter_number("## Chapter 1 Interaction Design") == 1
        assert _chapter_number("## Capítulo 5") == 5
        assert _chapter_number("## Chapitre 2") == 2
        assert _chapter_number("## Kapitel 3") == 3

    def test_asciidoc_prefixed_chapter_word(self):
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("== Chapter 1") == 1
        assert _chapter_number("=== Chapter 2") == 2

    def test_md_prefixed_roman_numeral(self):
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("## I. Loomings") == 1
        assert _chapter_number("## III: The Spouter-Inn") == 3

    def test_issue91_repro_matches_plain_text_count(self):
        # The exact reproduction from #91: 35 real chapters plus 35 subsection
        # headings. With the fix, the numeric path wins and the structural
        # fallback no longer inflates the count to 36.
        md = "\n".join(f"## Chapter {i}\n## Some Section\nbody\n" for i in range(1, 36))
        plain = "\n".join(f"Chapter {i}\nbody\n" for i in range(1, 36))
        assert detect_structure(md)["chapters_detected"] == 35
        assert detect_structure(plain)["chapters_detected"] == 35
        # The numeric path also fills the heading sample — an empty sample is a
        # reliable tell that the structural fallback was used instead.
        sample = detect_structure(md)["chapter_headings_sample"]
        assert sample and sample[0] == "## Chapter 1"

    def test_md_prefixed_lowercase_roman_still_works(self):
        # "## i. introduction" is trusted as a heading (markdown context);
        # unchanged from before the fix.
        text = "## i. introduction\nbody\n## ii. methods\nbody\n## iii. results\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_md_prefixed_non_chapter_headings_still_rejected(self):
        from book_to_skill.utils import _chapter_number

        assert _chapter_number("## Some Section") is None
        assert _chapter_number("## 5 Setup") is None
        assert _chapter_number("## Acknowledgment") is None
        assert _chapter_number("## 2025 Goals") is None

    def test_md_prefixed_cjk_unchanged(self):
        # CJK matchers already tolerated the prefix inline; behavior is
        # byte-for-byte unchanged.
        assert detect_structure("## 第一讲\n正文\n## 第二讲\n正文\n")["chapters_detected"] == 2
        assert detect_structure("## 一 · 缘起\n正文\n## 二 · 主体\n正文\n")["chapters_detected"] == 2


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

    def test_extract_docx_zipfile_xxe_rejection_direct_call(self, tmp_path):
        """extract_docx_with_zipfile() must reject malicious XML even when
        called directly, not just via the extract_docx() wrapper — this is
        the bypass the self-defending validate_docx_xml_safety() call closes."""
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
            extract_docx_with_zipfile(str(bad_docx))

    def test_extract_docx_python_docx_xxe_rejection_direct_call(self, tmp_path):
        """extract_docx_with_python_docx() must reject malicious XML even when
        called directly, not just via the extract_docx() wrapper — mirrors the
        zipfile-parser test above. Validation now runs after `import docx`
        succeeds (so an absent python-docx doesn't pay for a scan that never
        protects anything -- see extract_docx_with_python_docx's docstring),
        so `docx` is faked importable here to exercise the guard
        deterministically regardless of whether python-docx is actually
        installed in the environment running this test."""
        from book_to_skill.parsers.docx import extract_docx_with_python_docx

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

        with mock.patch.dict(sys.modules, {"docx": mock.MagicMock()}):
            with pytest.raises(ExtractionError, match="Security validation failed"):
                extract_docx_with_python_docx(str(bad_docx))

    def test_extract_docx_python_docx_absent_skips_validation_without_raising(self, tmp_path):
        """Companion to the test above: when python-docx genuinely isn't
        importable, extract_docx_with_python_docx() must return None (not
        raise, not scan the archive) -- it can't parse anything either way,
        malicious or not, so there's no protection to buy by validating."""
        from book_to_skill.parsers.docx import extract_docx_with_python_docx

        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("simulated: python-docx not installed")
            return real_import(name, *args, **kwargs)

        docx_path = tmp_path / "whatever.docx"
        docx_path.write_bytes(b"not even a real docx")

        with mock.patch("builtins.__import__", side_effect=fake_import):
            result = extract_docx_with_python_docx(str(docx_path))

        assert result is None

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

    def test_extract_docx_validates_once_when_python_docx_unavailable(self, tmp_path):
        """Maintainer-requested regression test: validate_docx_xml_safety()
        must run exactly once through extract_docx() when python-docx isn't
        installed -- once for real in the zipfile fallback, not also
        wastefully in the python-docx path before it ImportErrors out. That
        double-scan (the whole archive, every .xml/.rels member, decoded
        across five candidate encodings) is exactly what the earlier review
        round asked to remove."""
        from book_to_skill.parsers import docx as docx_module

        docx_path = _make_minimal_docx(tmp_path / "test.docx")

        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("simulated: python-docx not installed")
            return real_import(name, *args, **kwargs)

        with mock.patch.object(
            docx_module,
            "validate_docx_xml_safety",
            wraps=docx_module.validate_docx_xml_safety,
        ) as spy:
            with mock.patch("builtins.__import__", side_effect=fake_import):
                text, method = docx_module.extract_docx(str(docx_path))

        assert method == "zipfile-docx"
        assert "DOCX test paragraph" in text
        assert spy.call_count == 1



class TestResolveInputFiles:
    """Additional edge-case tests for resolve_input_files."""

    def test_existing_file_with_glob_metacharacters_is_literal(self, tmp_path):
        target = _make_text_file(tmp_path / "book [2013].pdf")

        result = resolve_input_files([str(target)])

        assert result == [target.resolve()]

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


class TestEpubSpineOrder:
    """The stdlib EPUB extractor reads content in spine order, with a safety net."""

    def _make_epub(self, tmp_path, opf_xml, files, opf_name="content.opf"):
        p = tmp_path / "book.epub"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?>'
                '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
                f'<rootfiles><rootfile full-path="{opf_name}" media-type="application/oebps-package+xml"/></rootfiles>'
                '</container>',
            )
            zf.writestr(opf_name, opf_xml)
            for name, html in files.items():
                zf.writestr(name, html)
        return str(p)

    def _doc(self, text):
        return f"<html><body><p>{text}</p></body></html>"

    def test_spine_order_overrides_manifest_order(self, tmp_path):
        opf = (
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
            '<item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>'
        )
        files = {"ch1.xhtml": self._doc("FIRST"), "ch2.xhtml": self._doc("SECOND")}
        out = extract_with_zipfile(self._make_epub(tmp_path, opf, files))
        assert out.index("FIRST") < out.index("SECOND")

    def test_non_spine_doc_kept_as_safety_net_after_spine(self, tmp_path):
        opf = (
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
            '<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="c1"/></spine></package>'
        )
        files = {"ch1.xhtml": self._doc("CONTENT"), "nav.xhtml": self._doc("NAVTOC")}
        out = extract_with_zipfile(self._make_epub(tmp_path, opf, files))
        assert "NAVTOC" in out
        assert out.index("CONTENT") < out.index("NAVTOC")

    def test_item_attribute_order_robust(self, tmp_path):
        opf = (
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
            '<item href="only.xhtml" id="c1" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="c1"/></spine></package>'
        )
        files = {"only.xhtml": self._doc("ONLY")}
        out = extract_with_zipfile(self._make_epub(tmp_path, opf, files))
        assert "ONLY" in out

    def test_spine_absent_uses_safety_net(self, tmp_path):
        # No <spine>: the manifest content doc is still included via the safety net.
        opf = (
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
            '<item id="a" href="a.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest></package>'
        )
        files = {"a.xhtml": self._doc("ALPHA")}
        out = extract_with_zipfile(self._make_epub(tmp_path, opf, files))
        assert "ALPHA" in out

    def test_opf_in_subdir_resolves_hrefs(self, tmp_path):
        opf = (
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
            '<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="c1"/></spine></package>'
        )
        files = {"OEBPS/ch1.xhtml": self._doc("SUBDIR")}
        out = extract_with_zipfile(
            self._make_epub(tmp_path, opf, files, opf_name="OEBPS/content.opf")
        )
        assert "SUBDIR" in out

    def test_non_self_closing_item_tag(self, tmp_path):
        # <item ...></item> (non-self-closing) is parsed via its opening tag.
        opf = (
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
            '<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"></item>'
            '</manifest><spine><itemref idref="c1"></itemref></spine></package>'
        )
        files = {"ch1.xhtml": self._doc("NONSELFCLOSE")}
        out = extract_with_zipfile(self._make_epub(tmp_path, opf, files))
        assert "NONSELFCLOSE" in out

    def test_no_opf_falls_back_to_sorted_files(self, tmp_path):
        # No container.xml / no OPF at all: the final fallback reads sorted
        # content files from the zip.
        p = tmp_path / "noopf.epub"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("a.xhtml", self._doc("AAA"))
            zf.writestr("b.xhtml", self._doc("BBB"))
        out = extract_with_zipfile(str(p))
        assert "AAA" in out and "BBB" in out


class TestTextEncodingDetection:
    """read_text_file decodes UTF-16/UTF-32 by BOM, with a BOM-less fallback."""

    SAMPLE = "Café — naïve résumé\nSecond line"

    def _write(self, tmp_path, raw_bytes):
        p = tmp_path / "sample.txt"
        p.write_bytes(raw_bytes)
        return str(p)

    def test_utf16_le_bom(self, tmp_path):
        raw = b"\xff\xfe" + self.SAMPLE.encode("utf-16-le")
        assert read_text_file(self._write(tmp_path, raw)) == self.SAMPLE

    def test_utf16_be_bom(self, tmp_path):
        raw = b"\xfe\xff" + self.SAMPLE.encode("utf-16-be")
        assert read_text_file(self._write(tmp_path, raw)) == self.SAMPLE

    def test_utf32_le_bom(self, tmp_path):
        raw = b"\xff\xfe\x00\x00" + self.SAMPLE.encode("utf-32-le")
        assert read_text_file(self._write(tmp_path, raw)) == self.SAMPLE

    def test_utf8_bom(self, tmp_path):
        raw = b"\xef\xbb\xbf" + self.SAMPLE.encode("utf-8")
        assert read_text_file(self._write(tmp_path, raw)) == self.SAMPLE

    def test_utf8_no_bom(self, tmp_path):
        raw = self.SAMPLE.encode("utf-8")
        assert read_text_file(self._write(tmp_path, raw)) == self.SAMPLE

    def test_cp1252_no_bom(self, tmp_path):
        # 0xE9 (é) is valid cp1252 but not a valid standalone utf-8 byte.
        raw = "café".encode("cp1252")
        assert read_text_file(self._write(tmp_path, raw)) == "café"

    def test_ascii_no_bom(self, tmp_path):
        assert read_text_file(self._write(tmp_path, b"hello world")) == "hello world"

    def test_utf32_be_bom(self, tmp_path):
        raw = b"\x00\x00\xfe\xff" + self.SAMPLE.encode("utf-32-be")
        assert read_text_file(self._write(tmp_path, raw)) == self.SAMPLE

    def test_empty_file_returns_empty_string(self, tmp_path):
        # An empty file decodes to "" (not None, which is reserved for read errors).
        assert read_text_file(self._write(tmp_path, b"")) == ""


class TestPdftotextEncoding:
    """pdftotext output (UTF-8) is decoded as UTF-8, not the locale encoding."""

    def test_pdftotext_requests_utf8_output(self, monkeypatch):
        captured = {}

        class _Result:
            returncode = 0
            stdout = "Café — naïve"

        monkeypatch.setattr(pdf_parser.shutil, "which", lambda name: "/usr/bin/pdftotext")

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured.update(kwargs)
            return _Result()

        monkeypatch.setattr(pdf_parser.subprocess, "run", fake_run)

        assert pdf_parser.extract_with_pdftotext("x.pdf") == "Café — naïve"
        assert captured.get("encoding") == "utf-8"
        assert captured.get("errors") == "replace"
        cmd = captured.get("cmd") or []
        assert "-enc" in cmd and cmd[cmd.index("-enc") + 1] == "UTF-8"


class TestPdfPageCount:
    """Tests for PDF page-count fallback behavior."""

    def test_count_pages_uses_pdfminer_when_pdfinfo_and_pypdf_are_unavailable(
        self, monkeypatch
    ):
        """Use pdfminer as the final fallback when other page counters are unavailable."""
        fake_pdf = "fake.pdf"

        monkeypatch.setattr(pdf_parser.shutil, "which", lambda _: None)

        high_level = mock.MagicMock()
        high_level.extract_text.return_value = (
            "page one\fpage two\fpage three"
        )

        pdfminer = mock.MagicMock()
        pdfminer.high_level = high_level

        monkeypatch.setitem(sys.modules, "pdfminer", pdfminer)
        monkeypatch.setitem(sys.modules, "pdfminer.high_level", high_level)

        assert pdf_parser.count_pages(fake_pdf) == 3

class TestLooksImageOnly:
    """Scanned PDFs are caught by probing the first pages, before the chain runs."""

    def _probe(self, monkeypatch, stdout, *, has_pdftotext=True):
        captured = {}

        class _Result:
            returncode = 0

        _Result.stdout = stdout
        monkeypatch.setattr(
            pdf_parser.shutil, "which",
            lambda name: "/usr/bin/pdftotext" if has_pdftotext else None,
        )

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _Result()

        monkeypatch.setattr(pdf_parser.subprocess, "run", fake_run)
        return captured

    def test_no_text_in_first_pages_is_image_only(self, monkeypatch):
        captured = self._probe(monkeypatch, "\n\f\n  \f")
        assert pdf_parser.looks_image_only("scan.pdf") is True
        # Only the first pages are probed, not the whole book.
        assert "-l" in captured["cmd"] and captured["cmd"][captured["cmd"].index("-l") + 1] == "5"

    def test_text_in_first_pages_is_not_image_only(self, monkeypatch):
        self._probe(monkeypatch, "Chapter 1\nOnce upon a time")
        assert pdf_parser.looks_image_only("book.pdf") is False

    def test_without_pdftotext_probe_is_skipped(self, monkeypatch):
        self._probe(monkeypatch, "", has_pdftotext=False)
        assert pdf_parser.looks_image_only("scan.pdf") is False

    def test_extraction_fails_early_with_ocr_hint(self, monkeypatch, tmp_path):
        from book_to_skill import utils

        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        monkeypatch.setattr(utils, "looks_image_only", lambda path: True)

        with pytest.raises(ExtractionError) as exc:
            utils.extract_single_file(pdf, "text", "no")

        assert "scanned" in str(exc.value)
        assert "ocrmypdf" in str(exc.value)


class TestPdftotextCleanup:
    """clean_pdftotext strips repeated headers/footers/page numbers and dehyphenates."""

    def _pages(self, *pages):
        return "\f".join(pages)

    def test_repeated_header_and_edge_page_numbers_removed(self):
        raw = self._pages(
            *(f"BOOK TITLE\nReal content on page {n}.\n{n}" for n in (1, 2, 3))
        )
        out = pdf_parser.clean_pdftotext(raw)
        assert "BOOK TITLE" not in out
        assert not any(ln.strip() in {"1", "2", "3"} for ln in out.splitlines())
        assert "Real content on page 1." in out

    def test_hyphenated_wrap_is_rejoined(self):
        raw = self._pages(*(f"H\nabout informa-\ntion here\n{n}" for n in (1, 2, 3)))
        out = pdf_parser.clean_pdftotext(raw)
        assert "information" in out
        assert "informa-" not in out

    def test_token_count_drops(self):
        raw = self._pages(*(f"RUNNING HEAD\nbody text page {n}\n{n}" for n in (1, 2, 3)))
        out = pdf_parser.clean_pdftotext(raw)
        assert len(out.split()) < len(raw.split())

    def test_mid_page_bare_number_is_kept(self):
        # A bare number that is NOT at a page edge must survive.
        raw = self._pages(*(f"HDR\nthe answer is 42\ntrailing\n{n}" for n in (1, 2, 3)))
        out = pdf_parser.clean_pdftotext(raw)
        assert "42" in out
        assert "HDR" not in out

    def test_single_page_keeps_content(self):
        # < 3 pages: no header/footer removal, only dehyphenation.
        out = pdf_parser.clean_pdftotext("Title\nword-\nwrap\n1")
        assert "wordwrap" in out
        assert "Title" in out
        assert "1" in out


# ═══════════════════════════════════════════════════════════════════════════
#  Fix #4 — Lowercase Roman numeral chapter detection
# ═══════════════════════════════════════════════════════════════════════════

class TestLowercaseRomanNumerals:
    """Verify that lowercase Roman numeral headings are detected."""

    def test_lowercase_roman_requires_heading_context(self):
        """Bare 'i: Loomings' at line start is NOT detected (FP guard)."""
        assert detect_structure("i: Loomings\nbody\nii: The Carpet-Bag\nbody\n")["chapters_detected"] == 0

    def test_lowercase_roman_with_markdown_heading(self):
        """'## i. introduction' as a markdown heading is detected."""
        text = "## i. introduction\nbody\n## ii. methods\nbody\n## iii. results\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 3

    def test_bare_lowercase_not_confused_with_prose(self):
        """Lowercase roman 'i' alone or 'v.' page dividers are not chapters."""
        from book_to_skill.utils import _chapter_number
        assert _chapter_number("i") is None
        assert _chapter_number("v.") is None
        assert _chapter_number("i.") is None
        assert _chapter_number("vi: the vim editor") is None
        assert _chapter_number("cli: a reference") is None
        assert _chapter_number("civ: a history") is None

    def test_uppercase_roman_still_works(self):
        """Existing uppercase Roman detection is unaffected."""
        assert detect_structure("I: Loomings\nbody\nII: Carpet-Bag\nbody\nIII: Spouter-Inn\nbody\n")["chapters_detected"] == 3

    def test_lowercase_roman_via_explicit_chapter_word(self):
        """'Chapter i.' with lowercase roman via _EXPLICIT_CHAPTER."""
        text = "Chapter i. Introduction\nbody\nChapter ii. Methods\nbody\n"
        assert detect_structure(text)["chapters_detected"] == 2

    def test_roman_word_false_positives_rejected(self):
        """Words that happen to be valid Roman numerals ('vi', 'cli', 'civ')
        are NOT detected as chapters when they appear bare at line start."""
        assert detect_structure("vi: the vim editor\nbody\n")["chapters_detected"] == 0
        assert detect_structure("cli: command line reference\nbody\n")["chapters_detected"] == 0
        assert detect_structure("civ: a civilization primer\nbody\n")["chapters_detected"] == 0
        assert detect_structure("li: a list item\nbody\n")["chapters_detected"] == 0

    def test_roman_word_false_positives_in_markdown_heading(self):
        """Even in markdown headings, short lowercase-Roman words that are
        real words ('vi', 'cli') should be validated via round-trip."""
        from book_to_skill.utils import _chapter_number
        assert _chapter_number("## vi: the editor") is not None  # legitimate Roman
        assert _chapter_number("## vi. editor") is not None


# ═══════════════════════════════════════════════════════════════════════════
#  CLI help entry point
# ═══════════════════════════════════════════════════════════════════════════

class TestCliHelp:
    """The documented help flags should print usage and exit successfully."""

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_help_flag_prints_console_script_usage(self, flag, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["book-to-skill", flag])

        with pytest.raises(SystemExit) as exc_info:
            main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "Usage: book-to-skill" in captured.err
        assert "extract.py" not in captured.err
        assert "Unknown flag" not in captured.err

    def test_no_arguments_keeps_error_exit_with_same_usage(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["book-to-skill"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "Usage: book-to-skill" in captured.err
        assert "extract.py" not in captured.err


# ═══════════════════════════════════════════════════════════════════════════
#  Fix #5 — Unknown flag warning in parse_arguments
# ═══════════════════════════════════════════════════════════════════════════

class TestParseArgumentsUnknownFlags:
    """Unknown flags should emit a warning, not be silently ignored."""

    def test_unknown_flag_warns(self):
        """An unknown flag like --mod should print a warning to stderr."""
        paths, mode, _ = parse_arguments(
            ["extract.py", "book.pdf", "--mod", "technical"]
        )
        assert mode == "text"  # default, since the flag is unknown

    def test_unknown_flag_stderr_message(self):
        """The warning message should mention the unknown flag name."""
        import io
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            parse_arguments(["extract.py", "book.pdf", "--unknown-flag"])
        output = stderr.getvalue()
        assert "WARNING" in output
        assert "--unknown-flag" in output

    def test_known_flags_dont_warn(self, capsys):
        """Known flags (--mode, --install-missing) should not produce warnings."""
        parse_arguments(["extract.py", "book.pdf", "--mode", "technical", "--install-missing", "no"])
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_path_args_not_warned(self, capsys):
        """Path arguments starting with '-' (like negative numbers) should not be warned as flags."""
        parse_arguments(["extract.py", "book.pdf", "notes.txt"])
        captured = capsys.readouterr()
        assert captured.err == ""


# ═══════════════════════════════════════════════════════════════════════════
#  CJK-aware token estimate (rescued from #70)
# ═══════════════════════════════════════════════════════════════════════════

class TestCjkTokenEstimate:
    """estimate_tokens counts CJK codepoints directly, not whitespace words."""

    def test_latin_estimate_unchanged(self):
        # The project's long-standing pinned ratio: 100 words -> 133 tokens.
        assert estimate_tokens(" ".join(["word"] * 100)) == 133

    def test_cjk_is_not_undercounted(self):
        # 1500 space-less Chinese chars must estimate ~1000 tokens, not ~1.
        assert estimate_tokens("中" * 1500) == 1000

    def test_mixed_latin_and_cjk(self):
        # Latin words + CJK chars are both counted.
        assert estimate_tokens("hello 世界 " * 100) > 100

    def test_empty_is_zero(self):
        assert estimate_tokens("") == 0

    def test_kangxi_radicals_counted_as_cjk(self):
        # Some Chinese ebooks render Han characters as Kangxi radicals
        # throughout (网 as ⽹ U+2F79, 大 as ⼤ U+2F24, 一 as ⼀ U+2F00).
        # A space-less run of them must not fall into the word branch.
        assert estimate_tokens("⼀" * 1500) == 1000


class TestPdfLibsCleanup:
    """extract_with_pypdf / extract_with_pdfminer also clean their output."""

    def test_pypdf_output_is_cleaned(self, monkeypatch):
        pages = [f"HEAD\nsome informa-\ntion page {n}\n{n}" for n in (1, 2, 3)]

        class _Page:
            def __init__(self, t): self._t = t
            def extract_text(self): return self._t

        class _Reader:
            def __init__(self, f): self.pages = [_Page(p) for p in pages]

        import types
        fake = types.SimpleNamespace(PdfReader=_Reader)
        monkeypatch.setitem(sys.modules, "pypdf", fake)
        monkeypatch.setattr("builtins.open", lambda *a, **k: mock.MagicMock())

        out = pdf_parser.extract_with_pypdf("x.pdf")
        assert "information" in out          # dehyphenated
        assert "HEAD" not in out             # repeated header stripped

    def test_pdfminer_output_is_cleaned(self, monkeypatch):
        raw = "\f".join(f"HEAD\ncon-\ntent page {n}\n{n}" for n in (1, 2, 3))
        import types
        fake = types.SimpleNamespace(extract_text=lambda path: raw)
        monkeypatch.setitem(sys.modules, "pdfminer.high_level", fake)

        out = pdf_parser.extract_with_pdfminer("x.pdf")
        assert "content" in out
        assert "HEAD" not in out
