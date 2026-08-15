"""
EPUB images must not be dropped silently (issue #127).

Text-only extraction never writes images, so the loss is invisible unless the
pipeline counts them. These tests pin the count helper and the plumbing that
surfaces the count in metadata.json and in the run report.
"""

import json
import sys
import textwrap
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.epub import count_epub_images
from book_to_skill.utils import extract_single_file, main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_epub_with_images(path: Path, images: list[str]) -> Path:
    """EPUB whose OPF manifest declares ``images`` as image items."""
    items = "\n".join(
        f'<item id="img{i}" href="{name}" media-type="image/jpeg"/>'
        for i, name in enumerate(images)
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "content.opf",
            textwrap.dedent(
                f"""\
                <?xml version="1.0"?>
                <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
                  <metadata/>
                  <manifest>
                    <item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
                    {items}
                  </manifest>
                  <spine>
                    <itemref idref="ch1"/>
                  </spine>
                </package>
                """
            ),
        )
        zf.writestr(
            "chapter1.xhtml",
            "<html><body><p>Chapter with figures referenced by caption only.</p>"
            + "".join(f'<img src="{name}"/>' for name in images)
            + "</body></html>",
        )
        for name in images:
            zf.writestr(name, b"\xff\xd8\xff\xe0faketest")
    return path


def _make_epub_without_images(path: Path) -> Path:
    """Minimal EPUB with no image items in the manifest and no image files."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "content.opf",
            textwrap.dedent(
                """\
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
                """
            ),
        )
        zf.writestr(
            "chapter1.xhtml",
            "<html><body><p>Plain prose only.</p></body></html>",
        )
    return path


def _make_md_file(path: Path, content: str = "# Title\n\nPlain text body.") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# count_epub_images
# ---------------------------------------------------------------------------


class TestCountEpubImages:
    def test_counts_manifest_image_items(self, tmp_path):
        epub = _make_epub_with_images(
            tmp_path / "fig.epub", ["fig1.jpg", "fig2.jpg", "fig3.jpg"]
        )
        assert count_epub_images(str(epub)) == 3

    def test_counts_image_files_when_manifest_declares_none(self, tmp_path):
        """A producer that ships images but forgets the manifest must not
        under-report — the archive scan is the fallback."""
        epub = tmp_path / "loose.epub"
        with zipfile.ZipFile(epub, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("chapter1.xhtml", "<html><body><p>text</p></body></html>")
            zf.writestr("OEBPS/fig1.png", b"\x89PNGfaketest")
            zf.writestr("OEBPS/fig2.svg", b"<svg/>")
        assert count_epub_images(str(epub)) == 2

    def test_zero_for_imageless_epub(self, tmp_path):
        epub = _make_epub_without_images(tmp_path / "plain.epub")
        assert count_epub_images(str(epub)) == 0

    def test_zero_on_unreadable_archive(self, tmp_path):
        missing = tmp_path / "does-not-exist.epub"
        assert count_epub_images(str(missing)) == 0


# ---------------------------------------------------------------------------
# extract_single_file plumbing
# ---------------------------------------------------------------------------


class TestExtractSingleFileReportsImages:
    def test_image_epub_reports_images_dropped(self, tmp_path):
        epub = _make_epub_with_images(tmp_path / "fig.epub", ["fig1.jpg", "fig2.jpg"])
        result = extract_single_file(epub, "text", "no")
        assert result["format"] == "epub"
        assert result["images_dropped"] == 2

    def test_plain_epub_reports_zero(self, tmp_path):
        epub = _make_epub_without_images(tmp_path / "plain.epub")
        result = extract_single_file(epub, "text", "no")
        assert result["images_dropped"] == 0

    def test_non_epub_has_no_images_dropped_key(self, tmp_path):
        md = _make_md_file(tmp_path / "notes.md")
        result = extract_single_file(md, "text", "no")
        assert "images_dropped" not in result


# ---------------------------------------------------------------------------
# main(): metadata.json + run report
# ---------------------------------------------------------------------------


class TestMainSurfacesImageLoss:
    def _run(self, tmp_path, monkeypatch, *paths):
        out_dir = tmp_path / "output"
        out_text = out_dir / "full_text.txt"
        out_meta = out_dir / "metadata.json"
        monkeypatch.setattr(
            "sys.argv", ["extract.py", *map(str, paths), "--install-missing", "no"]
        )
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", out_dir)
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", out_text)
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", out_meta)
        monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)
        main()
        return out_text, out_meta

    def test_metadata_records_image_loss(self, tmp_path, monkeypatch, capsys):
        epub = _make_epub_with_images(tmp_path / "fig.epub", ["fig1.jpg", "fig2.jpg"])
        _, out_meta = self._run(tmp_path, monkeypatch, epub)

        meta = json.loads(out_meta.read_text(encoding="utf-8"))
        assert meta["images_dropped"] == 2
        assert meta["sources"][0]["images_dropped"] == 2

        # The loss is surfaced, not silent.
        assert "2 image(s) in the source were not extracted" in capsys.readouterr().out

    def test_metadata_omits_field_when_nothing_dropped(
        self, tmp_path, monkeypatch, capsys
    ):
        md = _make_md_file(tmp_path / "notes.md")
        _, out_meta = self._run(tmp_path, monkeypatch, md)

        meta = json.loads(out_meta.read_text(encoding="utf-8"))
        assert "images_dropped" not in meta
        assert "not extracted" not in capsys.readouterr().out

    def test_per_source_image_count_survives_multi_source(self, tmp_path, monkeypatch):
        epub = _make_epub_with_images(tmp_path / "fig.epub", ["fig1.jpg"])
        md = _make_md_file(tmp_path / "notes.md")
        _, out_meta = self._run(tmp_path, monkeypatch, epub, md)

        meta = json.loads(out_meta.read_text(encoding="utf-8"))
        assert meta["images_dropped"] == 1
        by_name = {src["filename"]: src for src in meta["sources"]}
        assert by_name["fig.epub"]["images_dropped"] == 1
        assert "images_dropped" not in by_name["notes.md"]
