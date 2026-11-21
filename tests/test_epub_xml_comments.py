"""EPUB XML comments must not supply package paths or reading-order items."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from book_to_skill.parsers import epub


ROOT = Path(__file__).resolve().parent.parent


def make_epub(path, *, container_comment=False, spine_comment=False, manifest_comment=False):
    container = (
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles>'
        + ('<!-- old package\n<rootfile full-path="decoy.opf"/>\n-->' if container_comment else '')
        + '<rootfile full-path="OEBPS/content.opf"/>'
        '</rootfiles></container>'
    )
    opf = (
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
        + ('<!-- <item id="draft" href="draft.xhtml"/> -->' if manifest_comment else '')
        + '<item id="first" href="z.xhtml"/><item id="second" href="a.xhtml"/>'
        '</manifest><spine>'
        + ('<!-- old ordering\n<itemref idref="second"/>\n-->' if spine_comment else '')
        + '<itemref idref="first"/><itemref idref="second"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("decoy.opf", "<package/>")
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/z.xhtml", "<p>First chapter</p>")
        archive.writestr("OEBPS/a.xhtml", "<p>Second chapter</p>")
        archive.writestr("OEBPS/draft.xhtml", "<p>Unlisted draft</p>")


class EpubXmlCommentTests(unittest.TestCase):
    def test_container_comments_do_not_override_live_rootfile(self):
        self.check_epub(container_comment=True)

    def test_spine_comments_do_not_change_order_or_count(self):
        self.check_epub(spine_comment=True)

    def test_commented_manifest_item_is_not_appended(self):
        self.check_epub(manifest_comment=True)

    def test_comment_free_input_still_works(self):
        self.check_epub()

    def check_epub(self, **options):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.epub"
            make_epub(source, **options)
            self.assertEqual(epub.extract_with_zipfile(str(source)),
                             "First chapter\n\nSecond chapter")
            self.assertEqual(epub.count_epub_chapters(str(source)), 2)

    def test_cli_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.epub"
            work = Path(tmp) / "work"
            make_epub(source, container_comment=True, spine_comment=True, manifest_comment=True)
            result = subprocess.run(
                [sys.executable, "-B", "-S", str(ROOT / "scripts" / "extract.py"),
                 str(source), "--install-missing", "no"],
                cwd=ROOT, env=dict(os.environ, BOOK_SKILL_WORKDIR=str(work), PYTHONIOENCODING="utf-8"),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = (work / "full_text.txt").read_text(encoding="utf-8")
            metadata = json.loads((work / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(text.endswith("First chapter\n\nSecond chapter"), repr(text))
            self.assertEqual(metadata["extraction_method"], "zipfile")
            self.assertEqual(metadata["sources"][0]["pages"], 2)
