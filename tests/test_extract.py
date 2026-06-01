import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract.py"
SPEC = importlib.util.spec_from_file_location("extract", SCRIPT_PATH)
extract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = extract
SPEC.loader.exec_module(extract)


class ExtractTests(unittest.TestCase):
    def test_txt_extraction_writes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "book.txt"
            source.write_text(
                "Contents\n\nChapter 1\nHello world from a text book.\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "work"

            extract.main([str(source), "--output-dir", str(output_dir)])

            metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["filename"], "book.txt")
            self.assertEqual(metadata["format"], "txt")
            self.assertEqual(metadata["extraction_method"], "plain-text")
            self.assertTrue(metadata["has_toc"])
            self.assertEqual(metadata["chapters_detected"], 1)
            self.assertEqual(metadata["output_text"], str(output_dir / "full_text.txt"))
            self.assertEqual(
                (output_dir / "full_text.txt").read_text(encoding="utf-8"),
                source.read_text(encoding="utf-8"),
            )

    def test_output_dir_flag_overrides_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "book.txt"
            source.write_text("Chapter 1\nOutput flag wins.\n", encoding="utf-8")
            env_dir = tmp_path / "env-work"
            flag_dir = tmp_path / "flag-work"
            old_env = os.environ.get("BOOK_SKILL_WORKDIR")
            os.environ["BOOK_SKILL_WORKDIR"] = str(env_dir)
            try:
                extract.main([str(source), "--output-dir", str(flag_dir)])
            finally:
                if old_env is None:
                    os.environ.pop("BOOK_SKILL_WORKDIR", None)
                else:
                    os.environ["BOOK_SKILL_WORKDIR"] = old_env

            self.assertTrue((flag_dir / "full_text.txt").exists())
            self.assertTrue((flag_dir / "metadata.json").exists())
            self.assertFalse(env_dir.exists())

    def test_unsupported_extension_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "book.unsupported"
            source.write_text("plain text with a bad extension", encoding="utf-8")
            stderr = io.StringIO()

            with self.assertRaises(SystemExit) as exc_info:
                with contextlib.redirect_stderr(stderr):
                    extract.main([str(source), "--output-dir", str(tmp_path / "work")])

            self.assertEqual(exc_info.exception.code, 1)
            self.assertIn("Unsupported format '.unsupported'", stderr.getvalue())

    def test_default_install_mode_is_no(self):
        old_env = os.environ.pop("BOOK_SKILL_INSTALL_MISSING", None)
        try:
            args = extract.parse_args(["book.txt"])
        finally:
            if old_env is not None:
                os.environ["BOOK_SKILL_INSTALL_MISSING"] = old_env

        self.assertEqual(args.install_mode, "no")

    def test_env_and_flag_install_mode_resolution(self):
        cases = [
            ("ask", ["book.txt"], "ask"),
            ("yes", ["book.txt"], "yes"),
            ("no", ["book.txt", "--install-missing", "ask"], "ask"),
            ("ask", ["book.txt", "--install-missing", "no"], "no"),
            ("yes", ["book.txt", "--no-install-missing"], "no"),
        ]
        old_env = os.environ.get("BOOK_SKILL_INSTALL_MISSING")
        try:
            for env_value, argv, expected in cases:
                os.environ["BOOK_SKILL_INSTALL_MISSING"] = env_value
                with self.subTest(env_value=env_value, argv=argv):
                    args = extract.parse_args(argv)
                    self.assertEqual(args.install_mode, expected)
        finally:
            if old_env is None:
                os.environ.pop("BOOK_SKILL_INSTALL_MISSING", None)
            else:
                os.environ["BOOK_SKILL_INSTALL_MISSING"] = old_env


if __name__ == "__main__":
    unittest.main()
