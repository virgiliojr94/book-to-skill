"""Required RTF line breaks survive the dependency-free fallback."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from book_to_skill.parsers import rtf


ROOT = Path(__file__).resolve().parent.parent


class RtfLineBreakTests(unittest.TestCase):
    def test_line_break_consumes_only_its_delimiter_space(self):
        self.assertEqual(rtf.strip_rtf_fallback(r"{\rtf1 Alpha\line Beta}"), "Alpha\nBeta")
        self.assertEqual(rtf.strip_rtf_fallback(r"{\rtf1 Alpha\line  Beta}"), "Alpha\n Beta")

    def test_line_break_before_control_or_closing_group(self):
        self.assertEqual(rtf.strip_rtf_fallback(r"{\rtf1 Alpha\line\b Beta}"), "Alpha\nBeta")
        self.assertEqual(rtf.strip_rtf_fallback(r"{\rtf1 Alpha\line}"), "Alpha\n")

    def test_multiple_lines_keep_unicode_and_paragraph_controls(self):
        raw = r"{\rtf1 A\line caf\'e9\line \u945?\par Z}"
        self.assertEqual(rtf.strip_rtf_fallback(raw), "A\ncafé\nα\n Z")

    def test_longer_control_word_is_not_a_line_break(self):
        self.assertEqual(rtf.strip_rtf_fallback(r"{\rtf1 Alpha\linebetcol Beta}"), "AlphaBeta")

    def test_escaped_line_word_remains_literal(self):
        self.assertEqual(rtf.strip_rtf_fallback(r"{\rtf1 Show \\line literally}"), r"Show \line literally")

    def test_real_cli_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "synthetic.rtf"
            source.write_text(
                r"{\rtf1 Chapter 1\line First content\line Chapter 2\line Second content}",
                encoding="utf-8",
            )
            output = root / "work"
            env = os.environ.copy()
            env["BOOK_SKILL_WORKDIR"] = str(output)
            result = subprocess.run(
                [sys.executable, "-B", "-S", str(ROOT / "scripts" / "extract.py"),
                 str(source), "--mode", "text", "--install-missing", "no"],
                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            corpus = (output / "full_text.txt").read_text(encoding="utf-8")
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(corpus.endswith("Chapter 1\nFirst content\nChapter 2\nSecond content"))
            self.assertEqual(metadata["extraction_method"], "rtf-regex")
            self.assertEqual(metadata["chapters_detected"], 2)
