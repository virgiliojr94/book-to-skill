import json
import sys
import zipfile
from unittest import mock

from book_to_skill.utils import extract_single_file, main


def _make_epub_with_images(path, image_count=2):
    manifest_images = "\n".join(
        f'<item id="image-{index}" href="images/image-{index}.png" media-type="image/png"/>'
        for index in range(image_count)
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container><rootfiles><rootfile full-path="OEBPS/content.opf"/>'
            "</rootfiles></container>",
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<package><manifest><item id="chapter" href="chapter.xhtml" '
            'media-type="application/xhtml+xml"/>'
            f"{manifest_images}</manifest>"
            '<spine><itemref idref="chapter"/></spine></package>',
        )
        archive.writestr(
            "OEBPS/chapter.xhtml",
            "<html><body><h1>Chapter 1</h1><p>Extracted prose.</p></body></html>",
        )
        for index in range(image_count):
            archive.writestr(f"OEBPS/images/image-{index}.png", b"not-a-real-png")
    return path


def test_epub_extraction_reports_material_dropped_images(tmp_path, capsys):
    source = _make_epub_with_images(tmp_path / "figures.epub", image_count=6)

    with mock.patch("book_to_skill.utils.prepare_dependencies"):
        result = extract_single_file(source, "text", "no")

    assert result["images_dropped"] == 6
    stderr = capsys.readouterr().err
    assert "6 image(s)" in stderr
    assert "content is not extracted" in stderr


def test_epub_extraction_keeps_cover_only_book_quiet(tmp_path, capsys):
    source = _make_epub_with_images(tmp_path / "novel.epub", image_count=1)

    with mock.patch("book_to_skill.utils.prepare_dependencies"):
        result = extract_single_file(source, "text", "no")

    assert result["images_dropped"] == 1
    assert "content is not extracted" not in capsys.readouterr().err


def test_main_persists_epub_image_loss_in_source_and_total_metadata(
    tmp_path, monkeypatch
):
    source = _make_epub_with_images(tmp_path / "figures.epub", image_count=3)
    output_dir = tmp_path / "output"
    output_meta = output_dir / "metadata.json"

    monkeypatch.setattr(sys, "argv", ["extract.py", str(source), "--install-missing", "no"])
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", output_dir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", output_dir / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", output_meta)
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *args: None)

    main()

    metadata = json.loads(output_meta.read_text(encoding="utf-8"))
    assert metadata["images_dropped"] == 3
    assert metadata["sources"][0]["images_dropped"] == 3
