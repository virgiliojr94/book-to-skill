"""pdfinfo metadata must not hide the ASCII page-count line on legacy locales."""

import importlib.util
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from book_to_skill.parsers import pdf


class PdfinfoEncodingTests(unittest.TestCase):
    def emitted_page_count(self, payload):
        real_run = subprocess.run

        def emit_pdfinfo(command, **kwargs):
            self.assertEqual(command[0], "pdfinfo")
            self.assertTrue(os.path.isabs(command[-1]))
            return real_run(
                [sys.executable, "-c", "import sys; sys.stdout.buffer.write(" + repr(payload) + ")"],
                **kwargs,
            )

        # Python versions select their default pipe encoding via one of these
        # two paths. Force ASCII for this process only; the child emits bytes.
        with (patch.object(pdf.shutil, "which", return_value="pdfinfo"),
              patch.object(pdf.subprocess, "run", side_effect=emit_pdfinfo),
              patch.object(pdf.subprocess, "_text_encoding", return_value="ascii", create=True),
              patch.object(locale, "getpreferredencoding", return_value="ascii"),
              patch.dict(sys.modules, {"pypdf": None, "pdfminer.high_level": None})):
            return pdf.count_pages("synthetic.pdf")

    def test_utf8_metadata_does_not_discard_page_count(self):
        self.assertEqual(self.emitted_page_count("Title: 中文\nPages: 2\n".encode("utf-8")), 2)

    def test_malformed_metadata_byte_does_not_discard_page_count(self):
        self.assertEqual(self.emitted_page_count(b"Title: \xff\nPages: 2\n"), 2)

    def test_ascii_output_retains_page_count(self):
        self.assertEqual(self.emitted_page_count(b"Title: ordinary\nPages: 2\n"), 2)

    @unittest.skipUnless(shutil.which("pdfinfo") and importlib.util.find_spec("pypdf"),
                         "pdfinfo and pypdf needed for real-tool fixture")
    def test_real_pdfinfo_with_unicode_title(self):
        import pypdf

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic.pdf"
            writer = pypdf.PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.add_blank_page(width=100, height=100)
            writer.add_metadata({"/Title": "中文"})
            with source.open("wb") as stream:
                writer.write(stream)
            with (patch.object(pdf.subprocess, "_text_encoding", return_value="ascii", create=True),
                  patch.object(locale, "getpreferredencoding", return_value="ascii"),
                  patch.dict(sys.modules, {"pypdf": None, "pdfminer.high_level": None})):
                self.assertEqual(pdf.count_pages(str(source)), 2)
