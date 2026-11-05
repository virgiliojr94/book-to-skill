"""Synthetic EPUB XML attributes may have whitespace around '='."""

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


def make_epub(path, container_eq="=", manifest_eq="=", spine_eq="="):
    container = (
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        '<rootfiles><rootfile full-path' + container_eq + '"OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = (
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
        '<item id' + manifest_eq + '"second" href' + manifest_eq + '"a.xhtml"/>'
        '<item id' + manifest_eq + '"first" href' + manifest_eq + '"z.xhtml"/>'
        '</manifest><spine><itemref idref' + spine_eq + '"first"/>'
        '<itemref idref' + spine_eq + '"second"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("decoy.opf", "<package/>")
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/z.xhtml", "<p>First chapter</p>")
        archive.writestr("OEBPS/a.xhtml", "<p>Second chapter</p>")


class TestEpubXmlAttributeSpacing(unittest.TestCase):
    def test_spacing_in_container_manifest_and_spine(self):
        cases = (("=", "=", "="), (" = ", "=", "="),
                 ("=", " = ", "="), ("=", "=", " = "),
                 ("\n=\t", " \t=\n", "\r\n = "))
        with tempfile.TemporaryDirectory() as tmp:
            for container_eq, manifest_eq, spine_eq in cases:
                with self.subTest(container=container_eq, manifest=manifest_eq, spine=spine_eq):
                    source = Path(tmp) / "sample.epub"
                    make_epub(source, container_eq, manifest_eq, spine_eq)
                    self.assertEqual(epub.extract_with_zipfile(str(source)),
                                     "First chapter\n\nSecond chapter")
                    self.assertEqual(epub.count_epub_chapters(str(source)), 2)

    def test_real_cli_with_no_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.epub"
            output = Path(tmp) / "work"
            make_epub(source, " = ", " = ", " = ")
            env = dict(os.environ, BOOK_SKILL_WORKDIR=str(output), PYTHONIOENCODING="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", "-S", str(ROOT / "scripts" / "extract.py"),
                 str(source), "--mode", "text", "--install-missing", "no"],
                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            corpus = (output / "full_text.txt").read_text(encoding="utf-8")
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(corpus.endswith("First chapter\n\nSecond chapter"), repr(corpus))
            self.assertEqual(metadata["extraction_method"], "zipfile")
            self.assertEqual(metadata["sources"][0]["pages_label"], "spine_items")
            self.assertEqual(metadata["sources"][0]["pages"], 2)
