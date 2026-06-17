"""
Test that unexpected exceptions in parsers surface on stderr
while the fallback chain still returns None.
"""
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from extractor.parsers.pdf import extract_with_pypdf2


def test_pypdf2_warns_on_unexpected_error_and_returns_none(tmp_path, capsys):
    """Monkeypatch pypdf2 import to raise; confirm None + stderr warning."""
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 fake")

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "PyPDF2":
            raise RuntimeError("simulated failure")
        return real_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=fake_import):
        result = extract_with_pypdf2(str(broken))

    assert result is None
    captured = capsys.readouterr()
    assert "[warn]" in captured.err
    assert "failed:" in captured.err