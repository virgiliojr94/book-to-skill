"""Synthetic EPUB container paths containing XML character references."""

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


def make_epub(path, attribute, member):
    container = (
        '<container><rootfiles><rootfile full-path="' + attribute + '"/>'
        '</rootfiles></container>'
    )
    opf = (
        '<package><manifest><item id="z" href="z.xhtml"/>'
        '<item id="a" href="a.xhtml"/></manifest>'
        '<spine><itemref idref="z"/><itemref idref="a"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("decoy.opf", "<package/>")
        archive.writestr(member, opf)
        directory = member.rsplit("/", 1)[0]
        archive.writestr(directory + "/z.xhtml", "<p>First chapter</p>")
        archive.writestr(directory + "/a.xhtml", "<p>Second chapter</p>")


class TestEpubContainerEntities(unittest.TestCase):
    def test_entity_decoding_preserves_spine_order_and_count(self):
        cases = (("OEBPS/A&amp;B.opf", "OEBPS/A&B.opf"),
                 ("OEBPS/A&#38;B.opf", "OEBPS/A&B.opf"),
                 ("OEBPS/plain.opf", "OEBPS/plain.opf"),
                 ("OEBPS/A&#x26;B.opf", "OEBPS/A&B.opf"),
                 ("OEBPS/A&#x80;B.opf", "OEBPS/A\x80B.opf"),
                 ("OEBPS/A&copy;.opf", "OEBPS/A&copy;.opf"))
        with tempfile.TemporaryDirectory() as tmp:
            for attribute, member in cases:
                with self.subTest(attribute=attribute):
                    source = Path(tmp) / "synthetic.epub"
                    make_epub(source, attribute, member)
                    self.assertEqual(epub.extract_with_zipfile(str(source)),
                                     "First chapter\n\nSecond chapter")
                    self.assertEqual(epub.count_epub_chapters(str(source)), 2)

    def test_decoding_occurs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.epub"
            make_epub(source, "OEBPS/A&amp;amp;B.opf", "OEBPS/A&amp;B.opf")
            self.assertEqual(epub.count_epub_chapters(str(source)), 2)
            self.assertEqual(epub.extract_with_zipfile(str(source)),
                             "First chapter\n\nSecond chapter")

    def test_cli_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.epub"
            output = Path(tmp) / "work"
            make_epub(source, "OEBPS/A&amp;B.opf", "OEBPS/A&B.opf")
            env = dict(os.environ, BOOK_SKILL_WORKDIR=str(output), PYTHONIOENCODING="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", "-S", str(ROOT / "scripts" / "extract.py"),
                 str(source), "--mode", "text", "--install-missing", "no"],
                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            corpus = (output / "full_text.txt").read_text(encoding="utf-8")
            meta = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(corpus.endswith("First chapter\n\nSecond chapter"), repr(corpus))
            self.assertEqual(meta["extraction_method"], "zipfile")
