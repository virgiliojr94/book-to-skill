"""Page evidence is opt-in and must not mutate the legacy PDF outputs."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from book_to_skill import utils
from book_to_skill.parsers.pdf import (
    extract_pypdf_page_records,
    extract_with_pypdf,
)


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "pdf_page_provenance.pdf"


class PdfPageSidecarTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf is optional")
    def test_fixture_shows_page_boundaries_are_lost_in_legacy_text(self):
        legacy = extract_with_pypdf(str(FIXTURE))
        self.assertIn("Page one evidence: ALPHA", legacy)
        self.assertIn("Page two evidence: BETA", legacy)
        self.assertNotIn("\f", legacy)
        self.assertIn("0.207", legacy)
        self.assertIn("0.110", legacy)

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf is optional")
    def test_cli_opt_in_preserves_legacy_outputs_and_records_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            ordinary = self._run_cli(base / "ordinary")
            opted_in = self._run_cli(base / "opted-in", "--pdf-page-sidecar")

            self.assertEqual(
                (ordinary / "full_text.txt").read_bytes(),
                (opted_in / "full_text.txt").read_bytes(),
            )
            self.assertFalse((ordinary / "pdf_pages.json").exists())

            ordinary_meta = json.loads((ordinary / "metadata.json").read_text(encoding="utf-8"))
            opted_meta = json.loads((opted_in / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(ordinary_meta["sources"], opted_meta["sources"])
            self.assertEqual(ordinary_meta["pages"], 2)
            self.assertNotIn("pdf_pages", opted_meta)

            sidecar = json.loads((opted_in / "pdf_pages.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["schema_version"], 1)
            source = sidecar["sources"][0]
            self.assertEqual(source["status"], "ok")
            self.assertEqual(source["source_sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
            self.assertEqual(source["full_text_extraction_method"], opted_meta["extraction_method"])
            self.assertEqual([page["physical_page"] for page in source["pages"]], [1, 2])
            self.assertEqual([page["extraction_method"] for page in source["pages"]], ["pypdf", "pypdf"])
            self.assertIn("ALPHA", source["pages"][0]["text"])
            self.assertNotIn("BETA", source["pages"][0]["text"])
            self.assertIn("BETA", source["pages"][1]["text"])
            page_text = source["pages"][1]["text"]
            self.assertIn("0.207", page_text)
            self.assertIn("0.110", page_text)
            if "0.2070.110" in page_text:
                self.assertIn(
                    "possible_joined_decimal_cells",
                    source["pages"][1]["low_confidence_reasons"],
                )
                self.assertTrue(source["pages"][1]["requires_manual_review"])
            if opted_meta["extraction_method"] != "pypdf":
                self.assertIn(
                    "different_extractor_from_full_text",
                    source["pages"][1]["low_confidence_reasons"],
                )

    def test_different_main_extractor_is_flagged_without_changing_page_text(self):
        source = {
            "source_file": str(FIXTURE),
            "sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "format": "pdf",
            "pages": 2,
            "extraction_method": "docling",
        }
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(utils, "extract_pypdf_page_records", return_value=[{
                "physical_page": 1,
                "text": "0.2070.110",
                "extraction_method": "pypdf",
                "low_confidence_reasons": ["possible_joined_decimal_cells"],
            }]):
                path = utils.write_pdf_page_sidecar([source], Path(temporary))
            data = json.loads(path.read_text(encoding="utf-8"))["sources"][0]
        self.assertEqual(data["low_confidence_reasons"], ["page_count_mismatch"])
        self.assertEqual(data["pages"][0]["text"], "0.2070.110")
        self.assertIn("different_extractor_from_full_text", data["pages"][0]["low_confidence_reasons"])

    def test_changed_source_never_gets_page_evidence(self):
        source = {
            "source_file": str(FIXTURE),
            "sha256": "0" * 64,
            "format": "pdf",
            "pages": 2,
            "extraction_method": "pypdf",
        }
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(utils, "extract_pypdf_page_records") as extract:
                path = utils.write_pdf_page_sidecar([source], Path(temporary))
            data = json.loads(path.read_text(encoding="utf-8"))["sources"][0]
        extract.assert_not_called()
        self.assertEqual(data["status"], "unavailable")
        self.assertEqual(data["reason"], "source_changed_since_extraction")
        self.assertEqual(data["pages"], [])

    def test_page_text_is_sanitized_and_failed_pages_are_flagged(self):
        class Reader:
            pages = [
                SimpleNamespace(extract_text=lambda: "safe\u200b text"),
                SimpleNamespace(extract_text=lambda: (_ for _ in ()).throw(ValueError("bad page"))),
                SimpleNamespace(extract_text=lambda: "0.2070.110"),
            ]

        fake_pypdf = SimpleNamespace(PdfReader=lambda _stream: Reader())
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            records = extract_pypdf_page_records(str(FIXTURE))

        self.assertEqual(records[0]["text"], "safe text")
        self.assertIn("sanitized_invisible_text", records[0]["low_confidence_reasons"])
        self.assertEqual(records[1]["text"], "")
        self.assertIn("page_extraction_failed", records[1]["low_confidence_reasons"])
        self.assertEqual(records[2]["text"], "0.2070.110")
        self.assertIn("possible_joined_decimal_cells", records[2]["low_confidence_reasons"])
        self.assertTrue(records[2]["requires_manual_review"])

    def test_known_sidecar_option_does_not_change_parse_arguments_shape(self):
        self.assertEqual(
            utils.parse_arguments(["extract.py", "book.pdf", "--pdf-page-sidecar"]),
            (["book.pdf"], "text", "ask"),
        )

    @staticmethod
    def _run_cli(workdir: Path, *options: str) -> Path:
        env = os.environ.copy()
        env["BOOK_SKILL_WORKDIR"] = str(workdir)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "extract.py"), str(FIXTURE),
             "--mode", "text", "--install-missing", "no", *options],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return workdir
