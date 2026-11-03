"""Technical EPUB requests report the existing text-only extraction path."""

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from book_to_skill import utils


ROOT = Path(__file__).resolve().parent.parent
FALLBACK_REASON = "format_not_supported_in_technical_mode"


@pytest.fixture
def epub_path(tmp_path):
    path = tmp_path / "technical.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            'version="1.0"><rootfiles><rootfile full-path="OEBPS/book.opf" '
            'media-type="application/oebps-package+xml"/>'
            '</rootfiles></container>',
        )
        archive.writestr(
            "OEBPS/book.opf",
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            'unique-identifier="book-id"><metadata '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:identifier id="book-id">synthetic</dc:identifier>'
            '<dc:title>Synthetic technical book</dc:title>'
            '<dc:language>en</dc:language></metadata><manifest>'
            '<item id="chapter" href="chapter.xhtml" '
            'media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="chapter"/></spine></package>',
        )
        archive.writestr(
            "OEBPS/chapter.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Example</title>'
            '</head><body><h1>Chapter 1</h1><pre>answer = 42</pre>'
            '<table><tr><td>Input</td><td>Output</td></tr></table></body></html>',
        )
    return path


def _run_cli(paths, output, mode=None):
    env = os.environ.copy()
    env["BOOK_SKILL_WORKDIR"] = str(output)
    command = [sys.executable, "-B", "-S", str(ROOT / "scripts" / "extract.py")]
    command.extend(str(path) for path in paths)
    command.extend(["--install-missing", "no"])
    if mode is not None:
        command.extend(["--mode", mode])
    result = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    text = (output / "full_text.txt").read_text(encoding="utf-8")
    return result, metadata, text


def test_technical_epub_cli_reports_fallback_and_retains_text_mode_output(epub_path, tmp_path):
    technical, metadata, text = _run_cli([epub_path], tmp_path / "technical", "technical")
    normal, normal_metadata, normal_text = _run_cli([epub_path], tmp_path / "text", "text")

    assert metadata["extraction_mode"] == "technical"
    assert metadata["extraction_method"] == "zipfile"
    assert metadata["sources"][0]["fallback_reason"] == FALLBACK_REASON
    assert "WARNING:" in technical.stderr
    assert "EPUB" in technical.stderr
    assert "Layout-aware extraction was not used" in technical.stderr
    assert "Layout-aware extraction was not used" not in technical.stdout
    assert normal_metadata["sources"][0]["fallback_reason"] is None
    assert "Layout-aware extraction was not used" not in normal.stderr
    assert text == normal_text
    assert "answer = 42" in text
    assert "Input" in text and "Output" in text


def test_default_epub_cli_remains_text_only_without_a_technical_warning(epub_path, tmp_path):
    result, metadata, text = _run_cli([epub_path], tmp_path / "default")

    assert metadata["extraction_mode"] == "text"
    assert metadata["sources"][0]["fallback_reason"] is None
    assert "Layout-aware extraction was not used" not in result.stderr
    assert "answer = 42" in text


def test_mixed_sources_record_the_technical_epub_reason_per_source(epub_path, tmp_path):
    markdown = tmp_path / "notes.md"
    markdown.write_text("# Notes\n\nExisting Markdown content.", encoding="utf-8")

    result, metadata, text = _run_cli([epub_path, markdown], tmp_path / "mixed", "technical")

    assert metadata["extraction_method"] == "multi-method"
    assert metadata["sources"][0]["fallback_reason"] == FALLBACK_REASON
    assert metadata["sources"][1]["fallback_reason"] is None
    assert result.stderr.count("Layout-aware extraction was not used") == 1
    assert "answer = 42" in text and "Existing Markdown content." in text


@pytest.mark.parametrize("mode", ["technical", "text"])
def test_ebooklib_keeps_its_text_and_reports_the_requested_mode(epub_path, monkeypatch, capsys, mode):
    pytest.importorskip("ebooklib")
    pytest.importorskip("bs4")
    monkeypatch.setattr(utils, "prepare_dependencies", lambda *_: None)

    def unexpected_docling(_path):
        pytest.fail("EPUB extraction must not invoke Docling")

    monkeypatch.setattr(utils, "extract_with_docling", unexpected_docling)
    result = utils.extract_single_file(epub_path, mode, "no")

    assert result["extraction_method"] == "ebooklib"
    assert result["fallback_reason"] == (FALLBACK_REASON if mode == "technical" else None)
    assert "answer = 42" in result["text"]
    assert ("Layout-aware extraction was not used" in capsys.readouterr().err) == (mode == "technical")


@pytest.mark.parametrize("name", ["BOOK.EPUB", "book.unknown"])
def test_detected_epub_uses_its_format_for_the_warning(epub_path, tmp_path, monkeypatch, capsys, name):
    renamed = tmp_path / name
    epub_path.rename(renamed)
    monkeypatch.setattr(utils, "prepare_dependencies", lambda *_: None)
    monkeypatch.setattr(utils, "extract_with_ebooklib", lambda *_: None)

    result = utils.extract_single_file(renamed, "technical", "no")

    assert result["format"] == "epub"
    assert result["extraction_method"] == "zipfile"
    assert result["fallback_reason"] == FALLBACK_REASON
    assert "Layout-aware extraction was not used" in capsys.readouterr().err
