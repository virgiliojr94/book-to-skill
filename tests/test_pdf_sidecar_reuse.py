"""PDF page evidence must not survive a later run with different output."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from book_to_skill import utils


ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "tests" / "fixtures" / "pdf_page_provenance.pdf"


class PdfSidecarReuseTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf is optional")
    def test_reused_workdir_drops_prior_pdf_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            source = root / "other.md"
            source.write_text("# Chapter 1\nA different document.", encoding="utf-8")
            env = dict(os.environ, BOOK_SKILL_WORKDIR=str(work), PYTHONIOENCODING="utf-8")

            def run(path, *args):
                result = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "scripts" / "extract.py"),
                     str(path), "--install-missing", "no", *args],
                    cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            run(PDF, "--pdf-page-sidecar")
            sidecar = work / "pdf_pages.json"
            self.assertTrue(sidecar.is_file())
            self.assertTrue(json.loads(sidecar.read_text(encoding="utf-8"))["sources"])
            run(source)
            self.assertIn("A different document.", (work / "full_text.txt").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((work / "metadata.json").read_text(encoding="utf-8"))
                             ["sources"][0]["filename"], "other.md")
            self.assertFalse(sidecar.exists(), "old PDF evidence must not accompany new output")

    def test_unremovable_sidecar_does_not_replace_old_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "new.md"
            source.write_text("# New chapter\nNew content.", encoding="utf-8")
            work = root / "work"
            work.mkdir()
            old_text = work / "full_text.txt"
            old_text.write_text("previous output", encoding="utf-8")
            sidecar = work / "pdf_pages.json"
            sidecar.write_text("old evidence", encoding="utf-8")
            with (patch.object(utils, "OUTPUT_DIR", work),
                  patch.object(utils, "OUTPUT_TEXT", old_text),
                  patch.object(utils, "OUTPUT_META", work / "metadata.json"),
                  patch.object(sys, "argv", ["extract.py", str(source), "--install-missing", "no"]),
                  patch.object(Path, "unlink", side_effect=PermissionError("denied"))):
                with self.assertRaises(SystemExit) as failure:
                    utils.main()
            self.assertNotEqual(failure.exception.code, 0)
            self.assertEqual(old_text.read_text(encoding="utf-8"), "previous output")
            self.assertEqual(sidecar.read_text(encoding="utf-8"), "old evidence")

    def test_failed_new_sidecar_write_cannot_leave_previous_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "new.md"
            source.write_text("# New chapter\nNew content.", encoding="utf-8")
            work = root / "work"
            work.mkdir()
            sidecar = work / "pdf_pages.json"
            sidecar.write_text("old evidence", encoding="utf-8")
            with (patch.object(utils, "OUTPUT_DIR", work),
                  patch.object(utils, "OUTPUT_TEXT", work / "full_text.txt"),
                  patch.object(utils, "OUTPUT_META", work / "metadata.json"),
                  patch.object(sys, "argv", ["extract.py", str(source), "--install-missing", "no",
                                             "--pdf-page-sidecar"]),
                  patch.object(os, "replace", side_effect=OSError("simulated write failure"))):
                utils.main()
            self.assertFalse(sidecar.exists())
            self.assertIn("New content.", (work / "full_text.txt").read_text(encoding="utf-8"))
