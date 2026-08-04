"""metadata.json must be written as UTF-8, not in the host's locale encoding.

`main()` dumps the metadata with ``ensure_ascii=False``, so non-ASCII text is
passed through verbatim instead of being escaped to ``\\uXXXX``. Any CJK, Thai
or Korean chapter heading — or an accented filename or path — therefore reaches
the file encoder as-is. Without an explicit ``encoding=``, ``write_text()`` uses
the locale encoding and raises ``UnicodeEncodeError`` on a Windows cp1252 host
or under ``LC_ALL=C``.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import main


class TestMetadataOutputEncoding:
    # Two "第N章" headings, so chapters_detected is a meaningful assertion too.
    CJK_SOURCE = "第一章 緒論\n\nBody one.\n\n第二章 架構\n\nBody two.\n"

    def _run_main(self, tmp_path, monkeypatch):
        source = tmp_path / "cjk.md"
        source.write_text(self.CJK_SOURCE, encoding="utf-8")

        out_dir = tmp_path / "output"
        out_meta = out_dir / "metadata.json"
        monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(out_dir))
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", out_dir)
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", out_dir / "full_text.txt")
        monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", out_meta)
        monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)
        monkeypatch.setattr(
            "sys.argv", ["extract.py", str(source), "--install-missing", "no"]
        )

        main()
        return out_meta

    def test_metadata_write_declares_utf8(self, tmp_path, monkeypatch):
        """The metadata write must pass encoding="utf-8" explicitly.

        This is the platform-independent regression guard. On a UTF-8 host the
        locale default happens to produce the right bytes, so a round-trip
        assertion alone would pass on unfixed code in CI; only the declared
        encoding proves the fix. Mirrors TestPdftotextEncoding, which asserts
        the same way on the pdftotext subprocess call.
        """
        captured = {}
        original_write_text = Path.write_text

        def recording_write_text(self, data, encoding=None, **kwargs):
            if self.name == "metadata.json":
                captured["encoding"] = encoding
            return original_write_text(self, data, encoding=encoding, **kwargs)

        monkeypatch.setattr(Path, "write_text", recording_write_text)
        self._run_main(tmp_path, monkeypatch)

        assert captured.get("encoding") == "utf-8", (
            "metadata.json was written with the locale encoding; it must declare "
            'encoding="utf-8" because the JSON is dumped with ensure_ascii=False'
        )

    def test_non_ascii_headings_round_trip_as_utf8(self, tmp_path, monkeypatch):
        """The CJK headings survive the write and decode back as UTF-8."""
        out_meta = self._run_main(tmp_path, monkeypatch)

        meta = json.loads(out_meta.read_bytes().decode("utf-8"))
        assert meta["chapters_detected"] == 2
        assert "第一章 緒論" in meta["chapter_headings_sample"]
        assert "第二章 架構" in meta["chapter_headings_sample"]

    def test_metadata_is_valid_utf8_on_disk(self, tmp_path, monkeypatch):
        """The bytes on disk are UTF-8, whatever the host locale encoding is."""
        out_meta = self._run_main(tmp_path, monkeypatch)

        raw = out_meta.read_bytes()
        # Would raise UnicodeDecodeError if the file had been written as cp1252
        # or another single-byte codec that happened not to fail on write.
        decoded = raw.decode("utf-8")
        assert "第一章" in decoded
        assert "第一章 緒論".encode("utf-8") in raw
