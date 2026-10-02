"""The persisted corpus must not gain blank lines from newline translation."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from book_to_skill.utils import detect_structure


ROOT = Path(__file__).resolve().parent.parent
SOURCE = (
    "Alpha heading\n=============\n"
    "\talpha body line one\n  alpha body line two\n\n"
    "Beta heading\n============\n"
    "beta body line one\nbeta body line two\n"
)


@pytest.mark.parametrize(
    "source_bytes",
    [
        SOURCE.encode("utf-8"),
        SOURCE.replace("\n", "\r\n").encode("utf-8"),
        SOURCE.replace("\n", "\r").encode("utf-8"),
        SOURCE.replace("\n", "\r\n", 3).encode("utf-8"),
        SOURCE.replace("\n", "\r\n").encode("utf-8-sig"),
        SOURCE.replace("\n", "\r\n").encode("utf-16"),
        SOURCE.replace("\n", "\r\n").encode("utf-32"),
    ],
    ids=["lf", "crlf", "cr", "mixed", "utf8-bom-crlf", "utf16-crlf", "utf32-crlf"],
)
def test_cli_preserves_source_line_structure(tmp_path, source_bytes):
    source = tmp_path / "synthetic.md"
    source.write_bytes(source_bytes)
    output = tmp_path / "output"
    environment = dict(os.environ, BOOK_SKILL_WORKDIR=str(output))

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "extract.py"),
            str(source),
            "--mode",
            "text",
            "--install-missing",
            "no",
        ],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    original = detect_structure(SOURCE)
    raw = (output / "full_text.txt").read_bytes()
    reread = (output / "full_text.txt").read_text(encoding="utf-8")
    body = reread.split("=" * 80, 2)[-1].lstrip("\n")
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))

    assert b"\r\r\n" not in raw
    assert body == SOURCE.strip()
    assert len(body.splitlines()) == len(SOURCE.strip().splitlines())
    assert detect_structure(body)["chapters_detected"] == original["chapters_detected"] == 2
    assert metadata["chapters_detected"] == 2
    assert metadata["chars"] == len(raw.decode("utf-8"))


def test_corpus_writer_explicitly_disables_host_newline_translation(
    tmp_path, monkeypatch
):
    """The Linux CI leg must also pin the Windows-specific writer contract."""
    source = tmp_path / "synthetic.md"
    source.write_bytes(SOURCE.replace("\n", "\r\n").encode("utf-8"))
    output = tmp_path / "output"
    observed = []
    real_open = Path.open

    def record_open(self, mode="r", *args, **kwargs):
        if self.name == "full_text.txt" and mode == "w":
            observed.append(kwargs.get("newline"))
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", record_open)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", output)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", output / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", output / "metadata.json")
    monkeypatch.setattr("sys.argv", ["extract.py", str(source), "--install-missing", "no"])

    from book_to_skill.utils import main

    main()

    assert observed == ["\n"]
