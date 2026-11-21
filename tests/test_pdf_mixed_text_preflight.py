"""A textless PDF prefix does not prove that later pages lack text."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from book_to_skill import utils
from book_to_skill.parsers import pdf


ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "tests" / "fixtures" / "pdf_page_provenance.pdf"


class MixedPdfPreflightTests(unittest.TestCase):
    def probe(self, count, responses):
        with (patch.object(pdf.shutil, "which", return_value="pdftotext"),
              patch.object(pdf, "count_pages", return_value=count),
              patch.object(pdf.subprocess, "run", side_effect=responses) as run):
            value = pdf.looks_image_only("synthetic.pdf")
        return value, run

    def test_later_text_prevents_image_only_classification(self):
        value, run = self.probe(6, [SimpleNamespace(returncode=0, stdout="\f" * 5),
                                    SimpleNamespace(returncode=0, stdout="Later text\f")])
        self.assertFalse(value)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][1:3], ["-f", "6"])

    def test_all_probed_pages_empty_retains_scan_hint(self):
        value, _ = self.probe(6, [SimpleNamespace(returncode=0, stdout="\f" * 5),
                                  SimpleNamespace(returncode=0, stdout="\f")])
        self.assertTrue(value)

    def test_short_pdf_is_fully_covered_by_initial_probe(self):
        value, run = self.probe(2, [SimpleNamespace(returncode=0, stdout="\f\f")])
        self.assertTrue(value)
        self.assertEqual(run.call_count, 1)

    def test_unknown_page_count_or_failed_tail_probe_does_not_conclude(self):
        value, _ = self.probe(0, [SimpleNamespace(returncode=0, stdout="\f" * 5)])
        self.assertFalse(value)
        value, _ = self.probe(6, [SimpleNamespace(returncode=0, stdout="\f" * 5),
                                  SimpleNamespace(returncode=1, stdout="")])
        self.assertFalse(value)
        value, _ = self.probe(6, [SimpleNamespace(returncode=0, stdout="\f" * 5),
                                  subprocess.TimeoutExpired("pdftotext", 30)])
        self.assertFalse(value)

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf is optional")
    def test_real_pdf_reaches_fallback_when_later_page_has_text(self):
        import pypdf

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "mixed.pdf"
            writer = pypdf.PdfWriter()
            for _ in range(5):
                writer.add_blank_page(width=100, height=100)
            writer.add_page(pypdf.PdfReader(str(PDF)).pages[0])
            with source.open("wb") as stream:
                writer.write(stream)
            responses = [SimpleNamespace(returncode=0, stdout="\f" * 5),
                         SimpleNamespace(returncode=0, stdout="Page one evidence: ALPHA\f")]
            with (patch.object(pdf.shutil, "which", return_value="pdftotext"),
                  patch.object(pdf, "count_pages", return_value=6),
                  patch.object(pdf.subprocess, "run", side_effect=responses),
                  patch.object(utils, "prepare_dependencies"),
                  patch.object(utils, "extract_with_pdftotext", return_value=None),
                  patch.object(utils, "count_pages", return_value=6)):
                result = utils.extract_single_file(source, "text", "no")
            self.assertEqual(result["extraction_method"], "pypdf")
            self.assertIn("ALPHA", result["text"])
    @unittest.skipUnless(shutil.which("pdftotext") and importlib.util.find_spec("pypdf"),
                         "pdftotext and pypdf are required for synthetic PDF")
    def test_real_cli_extracts_text_after_five_textless_pages(self):
        import pypdf

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, work = root / "mixed.pdf", root / "work"
            writer = pypdf.PdfWriter()
            for _ in range(5):
                writer.add_blank_page(width=100, height=100)
            writer.add_page(pypdf.PdfReader(str(PDF)).pages[0])
            with source.open("wb") as stream:
                writer.write(stream)
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts" / "extract.py"), str(source),
                 "--mode", "text", "--install-missing", "no"],
                cwd=ROOT, env=dict(os.environ, BOOK_SKILL_WORKDIR=str(work), PYTHONIOENCODING="utf-8"),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ALPHA", (work / "full_text.txt").read_text(encoding="utf-8"))
