"""Page evidence inherits known source-level page count uncertainty."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from book_to_skill import utils


PDF = Path(__file__).resolve().parent / "fixtures" / "pdf_page_provenance.pdf"


class PdfPageCountConfidenceTests(unittest.TestCase):
    def sidecar(self, expected_count, method="pypdf", reasons=None):
        source = {
            "source_file": str(PDF),
            "sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
            "format": "pdf",
            "pages": expected_count,
            "extraction_method": method,
        }
        page = {"physical_page": 1, "text": "synthetic page", "extraction_method": "pypdf",
                "low_confidence_reasons": list(reasons or [])}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(utils, "extract_pypdf_page_records", return_value=[page]):
                result = utils.write_pdf_page_sidecar([source], Path(tmp))
            return json.loads(result.read_text(encoding="utf-8"))["sources"][0]

    def test_mismatch_requires_manual_review_on_each_page(self):
        source = self.sidecar(2)
        self.assertEqual(source["low_confidence_reasons"], ["page_count_mismatch"])
        page = source["pages"][0]
        self.assertIn("page_count_mismatch", page["low_confidence_reasons"])
        self.assertTrue(page["requires_manual_review"])

    def test_mismatch_preserves_other_page_warnings(self):
        page = self.sidecar(2, "docling", ["sanitized_invisible_text"])["pages"][0]
        self.assertEqual(set(page["low_confidence_reasons"]), {
            "page_count_mismatch", "different_extractor_from_full_text", "sanitized_invisible_text"
        })
        self.assertTrue(page["requires_manual_review"])

    def test_matching_or_unknown_source_count_does_not_trigger_mismatch(self):
        for count in (0, 1):
            with self.subTest(count=count):
                source = self.sidecar(count)
                self.assertNotIn("low_confidence_reasons", source)
                self.assertEqual(source["pages"][0]["low_confidence_reasons"], [])
                self.assertFalse(source["pages"][0]["requires_manual_review"])
