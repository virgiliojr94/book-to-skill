"""Tests for book_to_skill.remote.checkpoint (Contract C: remote_session.json & resume)."""

from __future__ import annotations

import ast
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.remote.checkpoint import (  # noqa: E402
    FORBIDDEN_PROSE_KEYS,
    SCHEMA_VERSION,
    SESSION_FILENAME,
    init_remote_session,
    load_remote_session,
    pending_chapters,
    save_remote_session,
    update_chapter_progress,
)
from book_to_skill.remote.reader import (  # noqa: E402
    parse_outline_response,
    read_section_from_pages,
)

posix_permissions = pytest.mark.skipif(
    not hasattr(os, "getuid"), reason="POSIX-only permission bits"
)


def _sample_work() -> dict:
    return {
        "provider": "libgen-mcp",
        "item_id": "work-123",
        "title": "Distributed\u200b Systems Design",
        "authors": ["Alice\u202e Author"],
        "edition": "1st ed.",
        "identifiers": {"isbn": ["9780134685991"], "doi": "10.1000/dist.1"},
        "text": "RAW COPYRIGHTED BOOK PROSE MUST NEVER BE SAVED",
        "raw_text": "SECRET RAW TEXT",
        "content": "SECRET CONTENT",
    }


def _sample_chapters() -> list[dict]:
    return [
        {"index": 1, "section_id": "ch1", "title": "Chapter 1\u200b: Foundations"},
        {"index": 2, "section_id": "ch2", "title": "Chapter 2: Consensus"},
        {"index": 3, "section_id": "ch3", "title": "Chapter 3: Storage"},
    ]


def test_checkpoint_module_has_zero_network_imports():
    checkpoint_path = ROOT_DIR / "book_to_skill" / "remote" / "checkpoint.py"
    tree = ast.parse(checkpoint_path.read_text(encoding="utf-8"))
    forbidden = {"urllib", "requests", "httpx", "socket", "http", "aiohttp"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(forbidden)


def test_init_remote_session_matches_contract_c_and_scrubs_prose():
    session = init_remote_session(
        _sample_work(),
        provider="libgen-mcp",
        outline_mode="outline",
        chapters=_sample_chapters(),
        confirmed_by_user=True,
        session_id="sess-001",
    )

    assert session["schema_version"] == SCHEMA_VERSION == 1
    assert session["session_id"] == "sess-001"
    assert session["provider"] == "libgen-mcp"
    assert session["confirmed_by_user"] is True
    assert session["outline_mode"] == "outline"
    assert session["limits"] == {"max_cursors_per_section": 100, "max_total_requests": 1000}

    # Sanitized metadata and zero raw prose keys
    assert session["work"]["title"] == "Distributed Systems Design"
    assert session["work"]["authors"] == ["Alice Author"]
    for forbidden_key in ("text", "raw_text", "content"):
        assert forbidden_key not in session["work"]

    assert session["chapters"] == [
        {
            "index": 1,
            "section_id": "ch1",
            "title": "Chapter 1: Foundations",
            "status": "pending",
            "next_cursor": None,
            "chunks_read": 0,
            "sanitized_removed_count": 0,
            "truncated": False,
            "error_reason": None,
        },
        {
            "index": 2,
            "section_id": "ch2",
            "title": "Chapter 2: Consensus",
            "status": "pending",
            "next_cursor": None,
            "chunks_read": 0,
            "sanitized_removed_count": 0,
            "truncated": False,
            "error_reason": None,
        },
        {
            "index": 3,
            "section_id": "ch3",
            "title": "Chapter 3: Storage",
            "status": "pending",
            "next_cursor": None,
            "chunks_read": 0,
            "sanitized_removed_count": 0,
            "truncated": False,
            "error_reason": None,
        },
    ]


@posix_permissions
def test_save_and_load_remote_session_enforces_0700_and_atomic_write(tmp_path):
    workdir = tmp_path / "run-ckpt"
    session = init_remote_session(
        _sample_work(),
        provider="libgen-mcp",
        outline_mode="outline",
        chapters=_sample_chapters(),
        confirmed_by_user=True,
        session_id="sess-save",
    )

    saved_path = save_remote_session(session, workdir)
    assert saved_path == workdir / SESSION_FILENAME
    assert saved_path.is_file()
    assert stat.S_IMODE(workdir.stat().st_mode) == 0o700
    assert stat.S_IMODE(saved_path.stat().st_mode) == 0o600
    assert [p.name for p in workdir.iterdir()] == [SESSION_FILENAME]

    loaded = load_remote_session(workdir)
    assert loaded == session


@posix_permissions
def test_save_remote_session_tightens_existing_dir_permissions(tmp_path):
    workdir = tmp_path / "loose-dir"
    workdir.mkdir()
    os.chmod(workdir, 0o777)

    session = init_remote_session(
        _sample_work(),
        provider="libgen-mcp",
        outline_mode="sequential_fallback",
        chapters=[],
        confirmed_by_user=True,
    )
    save_remote_session(session, workdir)
    assert stat.S_IMODE(workdir.stat().st_mode) == 0o700


def test_save_and_load_reject_symlinks(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link_dir = tmp_path / "link-dir"
    try:
        link_dir.symlink_to(real_dir, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks unavailable on host: {exc}")

    session = init_remote_session(
        _sample_work(),
        provider="libgen-mcp",
        outline_mode="outline",
        chapters=_sample_chapters(),
        confirmed_by_user=True,
    )

    with pytest.raises(ValueError, match="symbolic link"):
        save_remote_session(session, link_dir)

    with pytest.raises(ValueError, match="symbolic link"):
        load_remote_session(link_dir)

    # Symlinked remote_session.json inside a real workdir must also be rejected
    real_target = tmp_path / "outside.json"
    real_target.write_text("{}", encoding="utf-8")
    session_link = real_dir / SESSION_FILENAME
    session_link.symlink_to(real_target)

    with pytest.raises(ValueError, match="symbolic link"):
        save_remote_session(session, real_dir)

    with pytest.raises(ValueError, match="symbolic link"):
        load_remote_session(real_dir)


@posix_permissions
def test_save_and_load_reject_foreign_owner_dir(tmp_path, monkeypatch):
    workdir = tmp_path / "foreign"
    workdir.mkdir()
    real_getuid = os.getuid
    monkeypatch.setattr(os, "getuid", lambda: real_getuid() + 1)

    session = init_remote_session(
        _sample_work(),
        provider="libgen-mcp",
        outline_mode="outline",
        chapters=_sample_chapters(),
        confirmed_by_user=True,
    )
    with pytest.raises(ValueError, match="different user"):
        save_remote_session(session, workdir)

    with pytest.raises(ValueError, match="different user"):
        load_remote_session(workdir)


def test_save_remote_session_rejects_raw_prose_keys_anywhere(tmp_path):
    for key in ("text", "raw_text", "content"):
        session = init_remote_session(
            _sample_work(),
            provider="libgen-mcp",
            outline_mode="outline",
            chapters=_sample_chapters(),
            confirmed_by_user=True,
        )
        session["chapters"][0][key] = "Leaked copyrighted paragraph."
        with pytest.raises(ValueError, match="raw prose"):
            save_remote_session(session, tmp_path / f"dir-{key}")

        session_top = init_remote_session(
            _sample_work(),
            provider="libgen-mcp",
            outline_mode="outline",
            chapters=_sample_chapters(),
            confirmed_by_user=True,
        )
        session_top["work"][key] = "Leaked inside work metadata."
        with pytest.raises(ValueError, match="raw prose"):
            save_remote_session(session_top, tmp_path / f"work-{key}")


def test_atomic_save_preserves_prior_checkpoint_on_replace_failure(tmp_path, monkeypatch):
    workdir = tmp_path / "atomic"
    session = init_remote_session(
        _sample_work(),
        provider="libgen-mcp",
        outline_mode="outline",
        chapters=_sample_chapters(),
        confirmed_by_user=True,
        session_id="initial",
    )
    save_remote_session(session, workdir)

    updated = dict(session)
    updated["session_id"] = "corrupted-update"

    def fail_replace(_src, _dst):
        raise OSError("simulated disk error")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated disk error"):
        save_remote_session(updated, workdir)

    # Prior file remains valid and no temp files remain
    assert [p.name for p in workdir.iterdir()] == [SESSION_FILENAME]
    loaded = load_remote_session(workdir)
    assert loaded is not None
    assert loaded["session_id"] == "initial"


def test_load_remote_session_validates_missing_and_schema_version(tmp_path):
    assert load_remote_session(tmp_path / "nonexistent") is None
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert load_remote_session(empty_dir) is None

    bad_version_path = empty_dir / SESSION_FILENAME
    bad_version_path.write_text(json.dumps({"schema_version": 2, "chapters": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_remote_session(empty_dir)

    bool_version_path = empty_dir / SESSION_FILENAME
    bool_version_path.write_text(json.dumps({"schema_version": True, "chapters": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_remote_session(empty_dir)


def test_update_chapter_progress_and_resume_skips_done_chapters(tmp_path):
    mode, chapters = parse_outline_response(
        {
            "chapters": [
                {"section_id": "ch1", "title": "Ch 1"},
                {"section_id": "ch2", "title": "Ch 2"},
                {"section_id": "ch3", "title": "Ch 3"},
                {"section_id": "ch4", "title": "Ch 4"},
            ]
        }
    )
    assert mode == "outline"

    session = init_remote_session(
        _sample_work(),
        provider="libgen-mcp",
        outline_mode=mode,
        chapters=chapters,
        confirmed_by_user=True,
    )

    # ch1 finishes completely via reader helper; raw prose must NOT enter checkpoint
    ch1_res = read_section_from_pages(
        [{"text": "Confidential\u200b book prose for chapter 1.", "next_cursor": None}]
    )
    update_chapter_progress(session, "ch1", progress=ch1_res)

    # ch2 stops mid-pagination (e.g. max_total_requests reached) keeping next_cursor
    ch2_res = read_section_from_pages(
        [
            {"text": "Ch2 page 1", "next_cursor": "cur-2b"},
            {"text": "Ch2 page 2", "next_cursor": "cur-2c"},
        ],
        max_total_requests=1,
    )
    update_chapter_progress(session, "ch2", progress=ch2_res)

    # ch3 failed (missing)
    ch3_res = read_section_from_pages([{"missing": True}])
    update_chapter_progress(session, "ch3", progress=ch3_res)

    workdir = tmp_path / "resume-run"
    saved = save_remote_session(session, workdir)
    raw_disk = saved.read_text(encoding="utf-8")

    # Verify zero raw book text or forbidden prose keys on disk
    assert "Confidential book prose" not in raw_disk
    assert "Ch2 page 1" not in raw_disk
    parsed_disk = json.loads(raw_disk)
    for ch in parsed_disk["chapters"]:
        assert set(ch.keys()).isdisjoint(FORBIDDEN_PROSE_KEYS)

    resumed = load_remote_session(workdir)
    assert resumed is not None
    remaining = pending_chapters(resumed)

    # Done chapter (ch1) is skipped; incomplete/failed/pending remain with cursors/reasons
    assert [ch["section_id"] for ch in remaining] == ["ch2", "ch3", "ch4"]
    assert remaining[0]["status"] == "incomplete"
    assert remaining[0]["next_cursor"] == "cur-2b"
    assert remaining[1]["status"] == "failed"
    assert remaining[1]["error_reason"] is not None
    assert remaining[2]["status"] == "pending"
