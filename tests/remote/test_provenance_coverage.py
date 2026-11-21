"""Unit tests for book_to_skill.remote.coverage and book_to_skill.remote.provenance."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.remote.coverage import (  # noqa: E402
    COVERAGE_REPORT_KEYS,
    build_coverage_report,
    format_coverage_summary,
)
from book_to_skill.remote.policy import load_policy  # noqa: E402
from book_to_skill.remote.provenance import (  # noqa: E402
    FORBIDDEN_PROSE_KEYS,
    STORAGE_MODE,
    build_remote_provenance,
    render_provenance_markdown,
)
from tools.scan_generated_skill import _scan_text  # noqa: E402


def _sample_candidate(provider: str = "libgen-mcp") -> dict:
    return {
        "provider": provider,
        "item_id": "item-42",
        "title": "Systems Architecture Primer",
        "authors": ["Ada Lovelace", "Grace Hopper"],
        "edition": "2nd ed.",
        "year": 2024,
        "format": "epub",
        "language": "en",
        "identifiers": {
            "isbn": ["9780134685991"],
            "doi": "10.1000/example.42",
        },
        "source_name": "Open Technical Catalog",
        "access_info": "Read-only preview via MCP",
        "license_info": "All rights reserved",
        "dedup_key": "work:systems architecture primer|ada lovelace",
    }


def _sample_session(
    chapters: list[dict],
    *,
    outline_mode: str = "outline",
    confirmed_by_user: bool = True,
) -> dict:
    return {
        "schema_version": 1,
        "session_id": "sess-2026-01",
        "provider": "libgen-mcp",
        "work": {
            "item_id": "item-42",
            "title": "Systems Architecture Primer",
            "authors": ["Ada Lovelace", "Grace Hopper"],
            "edition": "2nd ed.",
            "identifiers": {
                "isbn": ["9780134685991"],
                "doi": "10.1000/example.42",
            },
        },
        "confirmed_by_user": confirmed_by_user,
        "outline_mode": outline_mode,
        "limits": {"max_cursors_per_section": 100, "max_total_requests": 1000},
        "chapters": chapters,
    }


def test_zero_network_imports_in_coverage_and_provenance():
    remote_dir = ROOT_DIR / "book_to_skill" / "remote"
    forbidden = {"urllib", "requests", "httpx", "socket", "http", "aiohttp"}

    for filename in ("coverage.py", "provenance.py"):
        py_file = remote_dir / filename
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    assert root_mod not in forbidden, f"Forbidden import {alias.name} in {filename}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                assert root_mod not in forbidden, f"Forbidden import {node.module} in {filename}"


def test_coverage_report_complete_run():
    session = _sample_session(
        [
            {
                "index": 1,
                "section_id": "ch01",
                "title": "Foundations",
                "status": "done",
                "next_cursor": None,
                "chunks_read": 4,
                "sanitized_removed_count": 0,
                "truncated": False,
                "error_reason": None,
            },
            {
                "index": 2,
                "section_id": "ch02",
                "title": "Replication",
                "status": "done",
                "next_cursor": None,
                "chunks_read": 6,
                "sanitized_removed_count": 1,
                "truncated": False,
                "error_reason": None,
            },
        ]
    )

    report = build_coverage_report(session)
    assert tuple(report.keys()) == COVERAGE_REPORT_KEYS
    assert report["chapters_total"] == 2
    assert report["chapters_done"] == 2
    assert report["chapters_incomplete"] == 0
    assert report["chapters_failed"] == 0
    assert report["missing_sections"] == []
    assert report["truncated_sections"] == []
    assert report["completeness_status"] == "complete"
    assert report["warnings"] == []

    summary = format_coverage_summary(report)
    assert "`complete`" in summary
    assert "2/2 chapters done" in summary
    assert "Missing sections" not in summary
    assert "Truncated sections" not in summary


def test_coverage_report_partial_and_truncated_run():
    session = _sample_session(
        [
            {
                "index": 1,
                "section_id": "ch01",
                "title": "Foundations",
                "status": "done",
                "chunks_read": 3,
                "truncated": False,
                "error_reason": None,
            },
            {
                "index": 2,
                "section_id": "ch02",
                "title": "Consensus",
                "status": "incomplete",
                "chunks_read": 5,
                "truncated": True,
                "error_reason": "max_cursors_per_section reached",
            },
            {
                "index": 3,
                "section_id": "ch03",
                "title": "Transactions",
                "status": "done",
                "chunks_read": 2,
                "truncated": True,
                "error_reason": "provider flagged truncated",
            },
        ]
    )

    report = build_coverage_report(session)
    assert report["chapters_total"] == 3
    assert report["chapters_done"] == 1
    assert report["chapters_incomplete"] == 2
    assert report["chapters_failed"] == 0
    assert report["missing_sections"] == []
    assert [sec["section_id"] for sec in report["truncated_sections"]] == ["ch02", "ch03"]
    assert report["completeness_status"] == "partial"
    assert len(report["warnings"]) == 2
    assert any("ch02" in w and "truncated" in w.lower() for w in report["warnings"])
    assert any("ch03" in w and "truncated" in w.lower() for w in report["warnings"])

    summary = format_coverage_summary(report)
    assert "`partial`" in summary
    assert "1/3 chapters done, 2 incomplete, 0 failed" in summary
    assert "Truncated sections:" in summary
    assert "ch02 (Consensus)" in summary
    assert "Coverage warnings:" in summary


def test_coverage_report_failed_and_missing_runs():
    # Case 1: All failed -> degraded
    all_failed_session = _sample_session(
        [
            {
                "index": 1,
                "section_id": "ch01",
                "title": "Intro",
                "status": "failed",
                "chunks_read": 0,
                "truncated": False,
                "error_reason": "section not found",
            },
            {
                "index": 2,
                "section_id": "ch02",
                "title": "Core",
                "status": "pending",
                "chunks_read": 0,
                "truncated": False,
                "error_reason": None,
            },
        ]
    )
    degraded = build_coverage_report(all_failed_session)
    assert degraded["chapters_total"] == 2
    assert degraded["chapters_done"] == 0
    assert degraded["chapters_incomplete"] == 1
    assert degraded["chapters_failed"] == 1
    assert [sec["section_id"] for sec in degraded["missing_sections"]] == ["ch01", "ch02"]
    assert degraded["completeness_status"] == "degraded"
    assert any("ch01" in w and "missing" in w.lower() for w in degraded["warnings"])
    assert any("ch02" in w and "missing" in w.lower() for w in degraded["warnings"])

    # Case 2: Majority failed (1 done, 2 failed) -> degraded
    majority_failed = _sample_session(
        [
            {"index": 1, "section_id": "ch01", "title": "One", "status": "done", "chunks_read": 2},
            {"index": 2, "section_id": "ch02", "title": "Two", "status": "failed", "error_reason": "timeout"},
            {"index": 3, "section_id": "ch03", "title": "Three", "status": "failed", "error_reason": "empty"},
        ]
    )
    majority_report = build_coverage_report(majority_failed)
    assert majority_report["completeness_status"] == "degraded"
    assert len(majority_report["missing_sections"]) == 2

    # Case 3: Empty chapters -> degraded with explicit warning
    empty_report = build_coverage_report(_sample_session([]))
    assert empty_report["chapters_total"] == 0
    assert empty_report["completeness_status"] == "degraded"
    assert len(empty_report["warnings"]) == 1

    # Case 4: Partial with 2 done and 1 failed -> partial
    partial_failed = _sample_session(
        [
            {"index": 1, "section_id": "ch01", "title": "One", "status": "done", "chunks_read": 2},
            {"index": 2, "section_id": "ch02", "title": "Two", "status": "done", "chunks_read": 2},
            {"index": 3, "section_id": "ch03", "title": "Three", "status": "failed", "error_reason": "404"},
        ]
    )
    partial_report = build_coverage_report(partial_failed)
    assert partial_report["completeness_status"] == "partial"
    assert [sec["section_id"] for sec in partial_report["missing_sections"]] == ["ch03"]


def test_coverage_report_sequential_fallback_warning():
    session = _sample_session(
        [
            {
                "index": 1,
                "section_id": "seq-01",
                "title": "Sequential Chunk 1",
                "status": "done",
                "chunks_read": 3,
                "truncated": False,
            }
        ],
        outline_mode="sequential_fallback",
    )

    report = build_coverage_report(session)
    assert report["completeness_status"] == "complete"
    assert any("sequential fallback" in w.lower() for w in report["warnings"])

    summary = format_coverage_summary(report)
    assert "Sequential fallback" in summary


def test_coverage_report_incomplete_non_truncated_and_sanitizes_invisible():
    session = _sample_session(
        [
            {
                "index": 1,
                "section_id": "ch01",
                "title": "Hidden\u200bTitle\u202e",
                "status": "incomplete",
                "chunks_read": 2,
                "truncated": False,
                "error_reason": "cursor_loop_\u200bdetected",
            }
        ]
    )

    report = build_coverage_report(session)
    assert report["chapters_incomplete"] == 1
    assert report["missing_sections"] == []
    assert report["truncated_sections"] == []
    assert report["completeness_status"] == "partial"
    assert len(report["warnings"]) == 1
    warning = report["warnings"][0]
    assert "\u200b" not in warning
    assert "\u202e" not in warning
    assert "cursor_loop_detected" in warning


def test_provenance_records_traceable_metadata_and_private_visibility_lock():
    candidate = _sample_candidate()
    session = _sample_session(
        [{"index": 1, "section_id": "ch01", "title": "Foundations", "status": "done", "chunks_read": 3}]
    )
    locked_policy = load_policy({"allow_public_publish": False})

    # Even if requested_visibility="public", policy locks visibility to "private".
    prov = build_remote_provenance(
        candidate,
        session,
        locked_policy,
        requested_visibility="public",
    )
    assert prov["provider"] == "libgen-mcp"
    assert prov["source_name"] == "Open Technical Catalog"
    assert prov["item_id"] == "item-42"
    assert prov["title"] == "Systems Architecture Primer"
    assert prov["authors"] == ["Ada Lovelace", "Grace Hopper"]
    assert prov["edition"] == "2nd ed."
    assert prov["year"] == 2024
    assert prov["format"] == "epub"
    assert prov["language"] == "en"
    assert prov["identifiers"] == {"isbn": ["9780134685991"], "doi": "10.1000/example.42"}
    assert prov["access_info"] == "Read-only preview via MCP"
    assert prov["license_info"] == "All rights reserved"
    assert prov["confirmed_by_user"] is True
    assert prov["publish_visibility"] == "private"
    assert prov["storage_mode"] == STORAGE_MODE
    assert prov["storage_mode"] == "incremental_ephemeral_no_full_text"
    assert prov["coverage"]["completeness_status"] == "complete"

    # Unlocked policy allows "public" only when requested as bare "public".
    unlocked_policy = load_policy({"allow_public_publish": True})
    prov_public = build_remote_provenance(
        candidate,
        session,
        unlocked_policy,
        requested_visibility="public",
    )
    assert prov_public["publish_visibility"] == "public"

    prov_sentence = build_remote_provenance(
        candidate,
        session,
        unlocked_policy,
        requested_visibility="it is public domain",
    )
    assert prov_sentence["publish_visibility"] == "private"


def test_provenance_never_stores_or_renders_raw_prose():
    secret_prose = "SYNTHETIC_COPYRIGHTED_PROSE_DO_NOT_PERSIST_991122"
    candidate = _sample_candidate()
    candidate["text"] = secret_prose
    candidate["raw_text"] = secret_prose
    candidate["content"] = secret_prose
    candidate["body"] = secret_prose
    candidate["excerpt"] = secret_prose

    session = _sample_session(
        [
            {
                "index": 1,
                "section_id": "ch01",
                "title": "Foundations",
                "status": "incomplete",
                "chunks_read": 1,
                "truncated": True,
                "error_reason": "cursor cap",
                "text": secret_prose,
                "raw_text": secret_prose,
                "content": secret_prose,
                "body": secret_prose,
            }
        ]
    )
    session["text"] = secret_prose
    session["full_text"] = secret_prose
    session["work"]["raw_text"] = secret_prose
    session["work"]["body"] = secret_prose

    coverage_with_prose = build_coverage_report(session)
    coverage_with_prose["raw_text"] = secret_prose
    coverage_with_prose["truncated_sections"][0]["body"] = secret_prose

    policy = load_policy()
    provenance = build_remote_provenance(candidate, session, policy, coverage=coverage_with_prose)

    serialized = json.dumps(provenance)
    assert secret_prose not in serialized

    def _collect_keys(obj: object) -> set[str]:
        keys: set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str):
                    keys.add(k.casefold())
                keys.update(_collect_keys(v))
        elif isinstance(obj, list):
            for item in obj:
                keys.update(_collect_keys(item))
        return keys

    assert _collect_keys(provenance).isdisjoint(FORBIDDEN_PROSE_KEYS)

    md = render_provenance_markdown(provenance)
    assert secret_prose not in md
    assert "Systems Architecture Primer" in md
    assert "Ada Lovelace, Grace Hopper" in md
    assert "9780134685991" in md
    assert "10.1000/example.42" in md
    assert "incremental_ephemeral_no_full_text" in md
    assert "`private`" in md
    assert "`partial`" in md


def test_provenance_falls_back_to_session_work_and_passes_skill_scanner():
    sparse_candidate = {"provider": "openlibrary-mcp", "title": "Sparse\u200b Book"}
    session = _sample_session(
        [
            {
                "index": 1,
                "section_id": "ch01",
                "title": "Chapter One",
                "status": "done",
                "chunks_read": 2,
            }
        ],
        confirmed_by_user=False,
    )
    policy = load_policy()

    prov = build_remote_provenance(sparse_candidate, session, policy)
    assert prov["title"] == "Sparse Book"
    assert prov["authors"] == ["Ada Lovelace", "Grace Hopper"]
    assert prov["edition"] == "2nd ed."
    assert prov["identifiers"]["isbn"] == ["9780134685991"]
    assert prov["confirmed_by_user"] is False

    md = render_provenance_markdown(prov)
    assert "\u200b" not in md
    findings = _scan_text("SKILL.md", f"## Scope & Limits\n\n{md}\n")
    assert findings == []


def test_coverage_and_provenance_reject_invalid_types():
    with pytest.raises(ValueError):
        build_coverage_report("not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_coverage_report({"chapters": "not-a-list"})
    with pytest.raises(ValueError):
        format_coverage_summary("not-a-dict")  # type: ignore[arg-type]

    policy = load_policy()
    session = _sample_session([])
    with pytest.raises(ValueError):
        build_remote_provenance("bad", session, policy)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_remote_provenance({}, "bad", policy)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_remote_provenance({}, session, "bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_remote_provenance({}, session, policy, coverage="bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        render_provenance_markdown("bad")  # type: ignore[arg-type]
