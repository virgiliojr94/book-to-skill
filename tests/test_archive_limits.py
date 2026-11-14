"""Small synthetic archives exercise document decompression limits."""

from __future__ import annotations

import struct
import json
import os
import subprocess
import sys
import types
import zlib
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from book_to_skill import archive as archive_limits
from book_to_skill import utils
from book_to_skill.archive import BoundedZipFile
from book_to_skill.exceptions import ExtractionError
from book_to_skill.parsers import docx, epub


def _write_archive(path: Path, members: dict[str, str | bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def _advertise_oversized_member(source: Path) -> None:
    # Advertise a large expanded member without allocating a decompression bomb.
    data = bytearray(source.read_bytes())
    central_header = data.index(b"PK\x01\x02")
    struct.pack_into("<I", data, central_header + 24, 32 * 1024 * 1024 + 1)
    source.write_bytes(data)


@pytest.mark.parametrize(
    ("parser", "member", "content"),
    [
        (epub.extract_with_zipfile, "chapter.xhtml", "<p>Normal text</p>"),
        (epub.count_epub_chapters, "content.opf", "<package/>"),
        (epub.count_epub_images, "image.png", b"small image fixture"),
        (
            docx.extract_docx_with_zipfile,
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body><w:p><w:r>'
            '<w:t>Normal text</w:t></w:r></w:p></w:body></w:document>',
        ),
    ],
)
def test_oversized_archive_member_is_rejected(
    tmp_path: Path, parser: Callable[[str], object], member: str, content: str | bytes
) -> None:
    source = _write_archive(tmp_path / "oversized.zip", {member: content})
    _advertise_oversized_member(source)

    with pytest.raises(ExtractionError, match="Archive .*limit"):
        parser(str(source))


@pytest.mark.parametrize("limit", ["MAX_ARCHIVE_MEMBERS", "MAX_TOTAL_BYTES"])
def test_archive_count_and_aggregate_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    source = _write_archive(tmp_path / "aggregate.zip", {"a": "abc", "b": "def"})
    monkeypatch.setattr(archive_limits, limit, 1 if limit == "MAX_ARCHIVE_MEMBERS" else 5)
    with pytest.raises(ExtractionError, match="Archive .*limit"):
        with BoundedZipFile(source):
            pytest.fail("An oversized archive was accepted")


def test_actual_read_budget_includes_repeated_member_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_archive(tmp_path / "repeated.zip", {"a": "abc", "b": "defg"})
    monkeypatch.setattr(archive_limits, "MAX_MEMBER_BYTES", 4)
    monkeypatch.setattr(archive_limits, "MAX_TOTAL_BYTES", 7)
    with BoundedZipFile(source) as archive:
        assert archive.read("a") == b"abc"
        assert archive.read("b") == b"defg"
        with pytest.raises(ExtractionError, match="Archive .*limit"):
            archive.read("a")


@pytest.mark.parametrize("compression", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_unsupported_compression_cannot_hide_expansion(
    tmp_path: Path, compression: int
) -> None:
    source = tmp_path / "hidden-expansion.zip"
    with zipfile.ZipFile(source, "w", compression=compression) as archive:
        archive.writestr("payload", b"a" * 1024)
    data = bytearray(source.read_bytes())
    central_header = data.index(b"PK\x01\x02")
    struct.pack_into("<I", data, central_header + 16, zlib.crc32(b"a" * 8))
    struct.pack_into("<I", data, central_header + 24, 8)
    source.write_bytes(data)
    with pytest.raises(ExtractionError, match="Archive compression"):
        with BoundedZipFile(source) as archive:
            archive.read("payload")


def test_ebooklib_repeated_manifest_hrefs_share_the_read_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("ebooklib")
    pytest.importorskip("bs4")
    monkeypatch.setattr(archive_limits, "MAX_MEMBER_BYTES", 8192)
    monkeypatch.setattr(archive_limits, "MAX_TOTAL_BYTES", 16384)
    members = {
        "mimetype": "application/epub+zip",
        "META-INF/container.xml": '<container xmlns="urn:oasis:names:tc:opendocument:'
        'xmlns:container"><rootfiles><rootfile full-path="content.opf" '
        'media-type="application/oebps-package+xml"/>'
        '</rootfiles></container>',
        "chapter.xhtml": "<html><body><p>Normal text</p></body></html>",
        "image.png": b"a" * 4096,
    }
    for repetitions in (1, 5):
        images = "".join(
            f'<item id="image-{index}" href="image.png" media-type="image/png"/>'
            for index in range(repetitions)
        )
        members["content.opf"] = (
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:title>Fixture</dc:title><dc:language>en</dc:language></metadata>'
            '<manifest><item id="chapter" href="chapter.xhtml" '
            'media-type="application/xhtml+xml"/>' + images + '</manifest>'
            '<spine><itemref idref="chapter"/></spine></package>'
        )
        source = _write_archive(tmp_path / f"repeated-{repetitions}.epub", members)
        if repetitions == 1:
            assert "Normal text" in epub.extract_with_ebooklib(str(source))
        else:
            with pytest.raises(ExtractionError, match="Archive .*limit"):
                epub.extract_with_ebooklib(str(source))


@pytest.mark.parametrize("parser", [epub.extract_with_ebooklib, docx.extract_docx_with_python_docx])
def test_optional_readers_reject_archives_before_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parser: Callable[[str], str | None]
) -> None:
    source = _write_archive(tmp_path / "optional.zip", {"payload.bin": b"small fixture"})
    _advertise_oversized_member(source)

    def unexpected_decode(*args: object) -> None:
        pytest.fail("The optional reader ran before archive validation")

    fake_epub = types.ModuleType("ebooklib.epub")
    fake_epub.EpubReader = unexpected_decode
    fake_ebooklib = types.ModuleType("ebooklib")
    fake_ebooklib.epub = fake_epub
    fake_bs4 = types.ModuleType("bs4")
    fake_bs4.BeautifulSoup = unexpected_decode
    fake_docx = types.ModuleType("docx")
    fake_docx.Document = unexpected_decode
    for name, module in (
        ("ebooklib", fake_ebooklib), ("ebooklib.epub", fake_epub),
        ("bs4", fake_bs4), ("docx", fake_docx),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    with pytest.raises(ExtractionError, match="Archive .*limit"):
        parser(str(source))


def test_unknown_extension_zip_sniff_is_bounded(tmp_path: Path) -> None:
    source = _write_archive(tmp_path / "renamed.data", {"mimetype": "application/epub+zip"})
    _advertise_oversized_member(source)
    with pytest.raises(ExtractionError, match="Archive .*limit"):
        utils.extract_single_file(source, "text", "no")


def test_epub_read_budget_refusal_does_not_return_partial_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    members = {
        "META-INF/container.xml": '<container><rootfile full-path="content.opf"/></container>',
        "content.opf": '<package><manifest><item id="good" href="chapter.xhtml"/>'
        '<item id="repeated" href="META-INF/container.xml"/></manifest><spine>'
        '<itemref idref="good"/><itemref idref="repeated"/></spine></package>',
        "chapter.xhtml": "<p>Normal text</p>",
    }
    source = _write_archive(tmp_path / "repeated.epub", members)
    monkeypatch.setattr(archive_limits, "MAX_TOTAL_BYTES", sum(len(s) for s in members.values()))
    with pytest.raises(ExtractionError, match="Archive .*limit"):
        epub.extract_with_zipfile(str(source))


def test_archive_rejection_preserves_other_batch_sources(tmp_path: Path) -> None:
    source = _write_archive(tmp_path / "oversized.epub", {"chapter.xhtml": "<p>Rejected</p>"})
    _advertise_oversized_member(source)
    good = tmp_path / "good.txt"
    good.write_text("Trusted batch source.", encoding="utf-8")
    output = tmp_path / "work"
    result = subprocess.run(
        [sys.executable, "-B", "-S", str(ROOT / "scripts/extract.py"),
         str(source), str(good), "--install-missing", "no"],
        cwd=ROOT, env=dict(os.environ, BOOK_SKILL_WORKDIR=str(output)),
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING: Skipping oversized.epub: Archive member size exceeds limit" in result.stderr
    text = (output / "full_text.txt").read_text(encoding="utf-8")
    assert "Trusted batch source." in text
    assert "Rejected" not in text
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert [source["filename"] for source in metadata["sources"]] == ["good.txt"]
