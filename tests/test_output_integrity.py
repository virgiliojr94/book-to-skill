"""Resuming requires the extraction output as well as unchanged sources."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from book_to_skill import utils


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def completed_run(tmp_path):
    """Use metadata emitted by the real CLI, not just a hand-built dict."""
    source = tmp_path / "synthetic.txt"
    source.write_text("Chapter 1: Synthetic\nVerify the corpus.\n", encoding="utf-8")
    work = tmp_path / "work"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "extract.py"), str(source),
         "--mode", "text", "--install-missing", "no"],
        env=dict(os.environ, BOOK_SKILL_WORKDIR=str(work)),
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    metadata = json.loads((work / "metadata.json").read_text(encoding="utf-8"))
    inputs = [(source, hashlib.sha256(source.read_bytes()).hexdigest())]
    return inputs, metadata, work / "full_text.txt"


def test_completed_corpus_digest_and_reuse(completed_run):
    inputs, metadata, corpus = completed_run
    assert metadata.get("output_text_sha256") == hashlib.sha256(corpus.read_bytes()).hexdigest()
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert ok, reason


@pytest.mark.parametrize("damage", ["missing", "empty", "truncated", "same-length"])
def test_damaged_output_cannot_resume(completed_run, damage):
    inputs, metadata, corpus = completed_run
    content = corpus.read_bytes()
    if damage == "missing":
        corpus.unlink()
    elif damage == "empty":
        corpus.write_bytes(b"")
    elif damage == "truncated":
        corpus.write_bytes(content[: len(content) // 2])
    else:
        corpus.write_bytes(b"x" * len(content))
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert not ok, f"{damage} corpus accepted: {reason}"
    expected = {"missing": "missing", "empty": "empty"}.get(damage, "changed")
    assert expected in reason


def test_legacy_output_digest_requires_fresh_extraction(completed_run):
    inputs, metadata, _ = completed_run
    metadata.pop("output_text_sha256", None)
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert not ok
    assert "legacy metadata" in reason
    assert "output" in reason


def test_missing_output_path_cannot_resume(completed_run):
    inputs, metadata, _ = completed_run
    metadata.pop("output_text")
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert not ok
    assert "path" in reason


def test_directory_instead_of_output_cannot_resume(completed_run):
    inputs, metadata, corpus = completed_run
    corpus.unlink()
    corpus.mkdir()
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert not ok
    assert "regular file" in reason


def test_unreadable_output_cannot_resume(completed_run, monkeypatch):
    inputs, metadata, _ = completed_run

    def unreadable(_path):
        raise PermissionError("synthetic read failure")

    # chmod is not a reliable unreadable-file probe on Windows/root runners.
    monkeypatch.setattr(utils, "_sha256_file", unreadable)
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert not ok
    assert "unreadable" in reason


def test_out_of_workdir_output_rejected_without_reading(completed_run, tmp_path, monkeypatch):
    inputs, metadata, _ = completed_run
    outside = tmp_path / "outside.txt"
    outside.write_text("not the extraction output", encoding="utf-8")
    metadata["output_text"] = str(outside)
    metadata["output_text_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()

    def must_not_read(_path):
        pytest.fail("out-of-workdir output must not be read")

    monkeypatch.setattr(utils, "_sha256_file", must_not_read)
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert not ok
    assert "outside" in reason


def test_symlink_out_of_workdir_output_rejected(completed_run, tmp_path, monkeypatch):
    inputs, metadata, corpus = completed_run
    outside = tmp_path / "outside.txt"
    outside.write_text("not the extraction output", encoding="utf-8")
    corpus.unlink()
    try:
        corpus.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks unavailable on this host: {exc}")

    def must_not_read(_path):
        pytest.fail("symlink to an outside corpus must not be read")

    monkeypatch.setattr(utils, "_sha256_file", must_not_read)
    ok, reason = utils.reuse_is_safe(inputs, metadata, "text")
    assert not ok
    assert "outside" in reason


def test_multi_chunk_non_ascii_output_records_actual_byte_digest(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.txt"
    source.write_bytes(("Synthetic 章节\r\n" * 160_000).encode("utf-8"))
    work = tmp_path / "work"
    corpus = work / "full_text.txt"
    monkeypatch.setattr(utils, "OUTPUT_DIR", work)
    monkeypatch.setattr(utils, "OUTPUT_TEXT", corpus)
    monkeypatch.setattr(utils, "OUTPUT_META", work / "metadata.json")
    monkeypatch.setattr("sys.argv", ["extract.py", str(source), "--mode", "text", "--install-missing", "no"])
    utils.main()
    metadata = json.loads((work / "metadata.json").read_text(encoding="utf-8"))
    raw = corpus.read_bytes()
    assert len(raw) > 2 << 20
    assert metadata.get("output_text_sha256") == hashlib.sha256(raw).hexdigest()
    ok, reason = utils.reuse_is_safe([(source, utils._sha256_file(str(source)))], metadata, "text")
    assert ok, reason
