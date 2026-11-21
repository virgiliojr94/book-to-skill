"""Preserve paragraph boundaries within DOCX table cells."""

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from book_to_skill.parsers import docx


ROOT = Path(__file__).resolve().parent.parent
NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(path):
    xml = (
        f'<w:document xmlns:w="{NS}"><w:body>'
        '<w:p><w:r><w:t>Before</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc>'
        '<w:p><w:r><w:t>First</w:t><w:tab/><w:t>term</w:t></w:r></w:p>'
        '<w:sdt><w:sdtContent><w:p><w:r><w:t>Second</w:t>'
        '<w:br/><w:t>line</w:t></w:r></w:p></w:sdtContent></w:sdt>'
        '</w:tc><w:tc><w:p><w:r><w:t>Value</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        '<w:p><w:r><w:t>After</w:t></w:r></w:p>'
        '</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


class DocxCellParagraphTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("docx"), "python-docx is optional")
    def test_generated_docx_preserves_multiple_paragraphs(self):
        import docx as python_docx

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "generated.docx"
            document = python_docx.Document()
            table = document.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "Alpha"
            table.cell(0, 0).add_paragraph("Beta")
            table.cell(0, 1).text = "Gamma"
            document.save(source)
            text = docx.extract_docx_with_zipfile(str(source))
        self.assertEqual(text, "Alpha\nBeta\tGamma")

    def test_fallback_keeps_paragraphs_and_inline_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.docx"
            make_docx(source)
            text = docx.extract_docx_with_zipfile(str(source))
        self.assertEqual(text, "Before\nFirst\tterm\nSecond\nline\tValue\nAfter")

    def test_cli_uses_fallback_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.docx"
            workdir = Path(tmp) / "work"
            make_docx(source)
            env = dict(os.environ, BOOK_SKILL_WORKDIR=str(workdir), PYTHONIOENCODING="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", "-S", str(ROOT / "scripts" / "extract.py"),
                 str(source), "--install-missing", "no"],
                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            corpus = (workdir / "full_text.txt").read_text(encoding="utf-8")
            metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(corpus.endswith("Before\nFirst\tterm\nSecond\nline\tValue\nAfter"))
            self.assertEqual(metadata["extraction_method"], "zipfile-docx")
