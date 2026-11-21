"""End-to-end tests for Mode 2 Search & Read using the offline Mock MCP simulator."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.remote.checkpoint import (  # noqa: E402
    SESSION_FILENAME,
    init_remote_session,
    load_remote_session,
    pending_chapters,
    save_remote_session,
    update_chapter_progress,
)
from book_to_skill.remote.coverage import (  # noqa: E402
    build_coverage_report,
    format_coverage_summary,
)
from book_to_skill.remote.discovery import (  # noqa: E402
    format_candidate_selection_table,
    group_duplicate_editions,
    normalize_search_results,
    normalize_work_details,
)
from book_to_skill.remote.policy import (  # noqa: E402
    build_access_copyright_notice,
    load_policy,
    verify_user_confirmation,
)
from book_to_skill.remote.provenance import (  # noqa: E402
    build_remote_provenance,
    render_provenance_markdown,
)
from book_to_skill.remote.reader import (  # noqa: E402
    parse_outline_response,
    read_section_from_pages,
)
from tests.remote.mock_mcp import (  # noqa: E402
    MockMCPCancelledError,
    MockMCPServer,
    MockMCPTimeoutError,
)


def _load_tool_module(module_name: str, rel_path: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, ROOT_DIR / rel_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


scan_tool = _load_tool_module("scan_generated_skill", "tools/scan_generated_skill.py")
validate_tool = _load_tool_module("validate_skill", "tools/validate_skill.py")


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "section"


def _synthesize_chapter_markdown(chapter: dict[str, Any], read_result: dict[str, Any]) -> str:
    """Synthesize a bounded chapter summary file and discard raw fragments."""
    title = chapter["title"]
    status = read_result["status"]
    sentences = [s.strip() for s in read_result["text"].split(".") if s.strip()]
    bullets = [f"- {sentence}." for sentence in sentences[:3]] or ["- No synthesized concepts available."]

    lines = [f"# {title}", ""]
    if status != "done" or read_result.get("truncated"):
        reason = read_result.get("error_reason") or f"chapter status is {status}"
        lines.extend(
            [
                f"> **Incomplete/Truncated Warning:** This section is `{status}` ({reason}).",
                "",
            ]
        )
    lines.extend(["## Key Concepts", *bullets, ""])
    return "\n".join(lines)


def _write_supporting_and_master_skill(
    skill_dir: Path,
    *,
    skill_name: str,
    title: str,
    chapter_files: list[tuple[str, str]],
    scope_limits_md: str,
) -> None:
    chapters_dir = skill_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    (skill_dir / "glossary.md").write_text(
        f"# {title} — Glossary\n\n- **Backpressure:** Upstream throttling driven by queue depth.\n",
        encoding="utf-8",
    )
    (skill_dir / "patterns.md").write_text(
        f"# {title} — Patterns\n\n- **Circuit Breaker:** Isolate failing dependencies quickly.\n",
        encoding="utf-8",
    )
    (skill_dir / "cheatsheet.md").write_text(
        f"# {title} — Cheatsheet\n\n- Set explicit timeout ceilings before adding retries.\n",
        encoding="utf-8",
    )

    chapter_index_lines = [
        f"- [{ch_title}](chapters/{ch_filename})" for ch_filename, ch_title in chapter_files
    ]
    skill_md = "\n".join(
        [
            "---",
            f"name: {skill_name}",
            f"description: Structured reference synthesized from {title}.",
            "---",
            "",
            f"# {title}",
            "",
            "## Core Frameworks & Mental Models",
            "",
            "- Explicit failure budgets, quorum consensus, and bounded queues.",
            "",
            "## Chapter Index",
            "",
            *chapter_index_lines,
            "",
            "## Topic Index",
            "",
            "- Resilience -> [Foundations](chapters/" + chapter_files[0][0] + ")",
            "",
            "## Supporting Files",
            "",
            "- [glossary.md](glossary.md)",
            "- [patterns.md](patterns.md)",
            "- [cheatsheet.md](cheatsheet.md)",
            "",
            "## Scope & Limits",
            "",
            scope_limits_md,
            "",
        ]
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")


def _details_match_candidate(candidate: dict[str, Any], details: dict[str, Any]) -> bool:
    """Detect metadata drift/inconsistency between search selection and get_details."""
    if candidate.get("title", "").casefold() != details.get("title", "").casefold():
        return False
    cand_authors = {a.casefold() for a in candidate.get("authors") or []}
    det_authors = {a.casefold() for a in details.get("authors") or []}
    if cand_authors and det_authors and cand_authors != det_authors:
        return False
    cand_isbns = set((candidate.get("identifiers") or {}).get("isbn") or [])
    det_isbns = set((details.get("identifiers") or {}).get("isbn") or [])
    if cand_isbns and det_isbns and cand_isbns.isdisjoint(det_isbns):
        return False
    return True


def _run_mock_mode2_pipeline(
    mcp: MockMCPServer,
    *,
    query: str,
    skill_dir: Path,
    workdir: Path,
    confirmation_reply: str = "yes",
    edition_index: int = 0,
    policy_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the full offline Mode 2 workflow against MockMCPServer."""
    policy = load_policy(policy_override)
    raw_hits = mcp.search(query)
    normalized_hits = normalize_search_results(raw_hits, provider=mcp.provider_name)
    grouped = group_duplicate_editions(normalized_hits)
    selection_table = format_candidate_selection_table(grouped)

    selected_group = grouped[0]
    variants = selected_group.get("editions") or [selected_group]
    selected_candidate = variants[edition_index]

    raw_details = mcp.get_details(selected_candidate["item_id"])
    details = normalize_work_details(raw_details, provider=mcp.provider_name)
    if not _details_match_candidate(selected_candidate, details):
        raise ValueError(
            f"Inconsistent metadata between search ({selected_candidate['title']!r}) "
            f"and get_details ({details['title']!r}); explicit re-selection required."
        )

    notice = build_access_copyright_notice(details, policy)
    if not verify_user_confirmation(confirmation_reply, details, policy):
        return {
            "aborted": True,
            "reason": "confirmation_denied",
            "notice": notice,
            "selection_table": selection_table,
            "policy": policy,
        }

    raw_outline = mcp.read(details["item_id"], mode="outline")
    outline_mode, chapters = parse_outline_response(raw_outline)
    if outline_mode == "sequential_fallback":
        chapters = [{"index": 1, "section_id": "seq-1", "title": "Sequential Segment 1"}]

    session = init_remote_session(
        details,
        provider=mcp.provider_name,
        outline_mode=outline_mode,
        chapters=chapters,
        confirmed_by_user=True,
    )
    save_remote_session(session, workdir)

    chapters_dir = skill_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    chapter_files: list[tuple[str, str]] = []

    for ch in chapters:
        sec_id = None if outline_mode == "sequential_fallback" else ch["section_id"]
        pages = mcp.iter_section_pages(details["item_id"], section_id=sec_id)
        res = read_section_from_pages(pages, max_cursors_per_section=session["limits"]["max_cursors_per_section"])
        update_chapter_progress(session, ch["section_id"], progress=res)
        save_remote_session(session, workdir)

        ch_filename = f"ch{ch['index']:02d}-{_slugify(ch['title'])}.md"
        (chapters_dir / ch_filename).write_text(
            _synthesize_chapter_markdown(ch, res),
            encoding="utf-8",
        )
        chapter_files.append((ch_filename, ch["title"]))
        # Discard raw fragments immediately after synthesizing chapter markdown.
        del res

    coverage = build_coverage_report(session)
    provenance = build_remote_provenance(details, session, policy, coverage=coverage)
    provenance_md = render_provenance_markdown(provenance)

    _write_supporting_and_master_skill(
        skill_dir,
        skill_name=_slugify(details["title"]),
        title=details["title"],
        chapter_files=chapter_files,
        scope_limits_md=provenance_md,
    )

    return {
        "aborted": False,
        "selection_table": selection_table,
        "notice": notice,
        "details": details,
        "session": session,
        "coverage": coverage,
        "provenance": provenance,
        "chapter_files": chapter_files,
    }


def test_mode1_offline_extract_smoke_and_mode2_structural_parity(tmp_path: Path):
    """Mode 1 (scripts/extract.py) works unchanged offline and shares Mode 2's output contract."""
    local_book = tmp_path / "synthetic-local-book.md"
    local_book.write_text(
        "# Synthetic Systems Design\n\n"
        "## Chapter 1: Foundations of Resilience\n\n"
        "Resilience begins with explicit failure budgets and bounded retries.\n\n"
        "## Chapter 2: Consensus and State\n\n"
        "Consensus protocols separate leader election from log replication.\n\n"
        "## Chapter 3: Storage and Backpressure\n\n"
        "Append-only logs maximize sequential write throughput.\n",
        encoding="utf-8",
    )
    mode1_workdir = tmp_path / "mode1-workdir"
    env = dict(os.environ)
    env["BOOK_SKILL_WORKDIR"] = str(mode1_workdir)

    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-S",
            str(ROOT_DIR / "scripts" / "extract.py"),
            str(local_book),
            "--install-missing",
            "no",
        ],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"Mode 1 extract.py failed: {proc.stderr}"
    assert (mode1_workdir / "full_text.txt").is_file()
    assert (mode1_workdir / "metadata.json").is_file()

    # Build Mode 1 skill tree from local extraction
    mode1_skill = tmp_path / "mode1-skill"
    mode1_chapters = [
        ("ch01-foundations-of-resilience.md", "Foundations of Resilience"),
        ("ch02-consensus-and-state.md", "Consensus and State"),
        ("ch03-storage-and-backpressure.md", "Storage and Backpressure"),
    ]
    (mode1_skill / "chapters").mkdir(parents=True)
    for fname, ch_title in mode1_chapters:
        (mode1_skill / "chapters" / fname).write_text(
            f"# {ch_title}\n\n## Key Concepts\n\n- Local Mode 1 synthesis.\n",
            encoding="utf-8",
        )
    _write_supporting_and_master_skill(
        mode1_skill,
        skill_name="synthetic-systems-design",
        title="Synthetic Systems Design",
        chapter_files=mode1_chapters,
        scope_limits_md="- Local Mode 1 extraction from synthetic-local-book.md.",
    )

    # Run Mode 2 offline via MockMCPServer
    mode2_skill = tmp_path / "mode2-skill"
    mode2_workdir = tmp_path / "mode2-workdir"
    mcp = MockMCPServer()
    result = _run_mock_mode2_pipeline(
        mcp,
        query="Synthetic Systems Design",
        skill_dir=mode2_skill,
        workdir=mode2_workdir,
    )
    assert result["aborted"] is False
    assert result["coverage"]["completeness_status"] == "complete"

    # Structural parity: exact same top-level and chapter file structure
    mode1_rel = sorted(p.relative_to(mode1_skill).as_posix() for p in mode1_skill.rglob("*") if p.is_file())
    mode2_rel = sorted(p.relative_to(mode2_skill).as_posix() for p in mode2_skill.rglob("*") if p.is_file())
    assert mode1_rel == mode2_rel

    # Mode 2 never writes full_text.txt or downloads original book files anywhere
    assert not list(tmp_path.glob("mode2-*/**/full_text.txt"))
    assert not (mode2_skill / "full_text.txt").exists()
    assert not (mode2_workdir / "full_text.txt").exists()
    assert not any(p.suffix in {".epub", ".pdf", ".mobi"} for p in mode2_skill.rglob("*"))
    assert not any(p.suffix in {".epub", ".pdf", ".mobi"} for p in mode2_workdir.rglob("*"))

    # Both skills pass generated-skill security scan and all 6 validate_skill lenses
    assert scan_tool.scan_generated_skill(mode1_skill) == []
    assert scan_tool.scan_generated_skill(mode2_skill) == []
    for lens in validate_tool.LENSES:
        err1, _ = validate_tool.audit(str(mode1_skill / "SKILL.md"), lens=lens)
        err2, _ = validate_tool.audit(str(mode2_skill / "SKILL.md"), lens=lens)
        assert err1 == [], f"Mode 1 validate_skill failed on {lens}: {err1}"
        assert err2 == [], f"Mode 2 validate_skill failed on {lens}: {err2}"


def test_full_search_and_read_workflow_selection_gate_and_denial(tmp_path: Path):
    """Exercises candidate grouping, explicit selection, copyright/cache notice, denial, and confirmation."""
    mcp = MockMCPServer()

    # 1. Refusal and ambiguous reply must abort BEFORE any MCP read() call
    denied_res = _run_mock_mode2_pipeline(
        mcp,
        query="Synthetic Systems Design",
        skill_dir=tmp_path / "denied-skill",
        workdir=tmp_path / "denied-work",
        confirmation_reply="no",
    )
    assert denied_res["aborted"] is True
    assert "2 editions" in denied_res["selection_table"]
    assert "does not equal copyright-holder authorization" in denied_res["notice"].casefold()
    assert "temporary server cache" in denied_res["notice"].casefold()
    assert all(call["op"] != "read" for call in mcp.call_log)
    assert not (tmp_path / "denied-work" / SESSION_FILENAME).exists()

    mcp.call_log.clear()
    ambiguous_res = _run_mock_mode2_pipeline(
        mcp,
        query="Synthetic Systems Design",
        skill_dir=tmp_path / "ambig-skill",
        workdir=tmp_path / "ambig-work",
        confirmation_reply="maybe later",
    )
    assert ambiguous_res["aborted"] is True
    assert all(call["op"] != "read" for call in mcp.call_log)

    # 2. Explicit confirmation proceeds through outline + cursor reading
    mcp.call_log.clear()
    skill_dir = tmp_path / "confirmed-skill"
    workdir = tmp_path / "confirmed-work"
    res = _run_mock_mode2_pipeline(
        mcp,
        query="Synthetic Systems Design",
        skill_dir=skill_dir,
        workdir=workdir,
        confirmation_reply="I confirm",
        edition_index=0,
    )
    assert res["aborted"] is False
    assert res["details"]["item_id"] == "syn-arch-epub-2"
    assert res["coverage"]["chapters_total"] == 3
    assert res["coverage"]["chapters_done"] == 3
    assert res["coverage"]["completeness_status"] == "complete"
    assert all(call["op"] != "download" for call in mcp.call_log)
    assert any(call["op"] == "read" and call["mode"] == "outline" for call in mcp.call_log)
    assert any(call["op"] == "read" and call["mode"] == "cursor" for call in mcp.call_log)

    # Verify zero raw prose in remote_session.json and provenance
    session_disk = (workdir / SESSION_FILENAME).read_text(encoding="utf-8")
    assert "Resilience begins with explicit failure budgets" not in session_disk
    assert "Consensus protocols separate leader election" not in session_disk
    assert "full_text" not in session_disk
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "incremental_ephemeral_no_full_text" in skill_text
    assert "`private`" in skill_text


def test_interrupted_session_resume_skips_done_chapters(tmp_path: Path):
    """Interrupted session resume skips done chapters and resumes incomplete cursor pagination."""
    mcp = MockMCPServer()
    workdir = tmp_path / "resume-workdir"
    details = normalize_work_details(mcp.get_details("syn-arch-epub-2"), provider="libgen-mcp")
    outline_mode, chapters = parse_outline_response(mcp.read("syn-arch-epub-2", mode="outline"))
    assert outline_mode == "outline"

    session = init_remote_session(
        details,
        provider="libgen-mcp",
        outline_mode=outline_mode,
        chapters=chapters,
        confirmed_by_user=True,
    )

    # Complete ch1
    ch1_res = read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch1"))
    assert ch1_res["status"] == "done"
    update_chapter_progress(session, "ch1", progress=ch1_res)

    # Interrupt ch2 after 1 request (leaving next_cursor="ch2-p2")
    ch2_partial = read_section_from_pages(
        mcp.iter_section_pages("syn-arch-epub-2", "ch2"),
        max_total_requests=1,
        requests_used=0,
    )
    assert ch2_partial["status"] == "incomplete"
    assert ch2_partial["next_cursor"] == "ch2-p2"
    update_chapter_progress(session, "ch2", progress=ch2_partial)
    save_remote_session(session, workdir)

    # Simulate fresh process resuming from remote_session.json
    mcp.call_log.clear()
    resumed = load_remote_session(workdir)
    assert resumed is not None
    to_process = pending_chapters(resumed)
    assert [ch["section_id"] for ch in to_process] == ["ch2", "ch3"]

    for ch in to_process:
        res = read_section_from_pages(
            mcp.iter_section_pages(
                "syn-arch-epub-2",
                ch["section_id"],
                start_cursor=ch["next_cursor"],
            )
        )
        assert res["status"] == "done"
        update_chapter_progress(resumed, ch["section_id"], progress=res)

    save_remote_session(resumed, workdir)

    # ch1 must NEVER be re-read; ch2 must resume directly from ch2-p2
    read_calls = [c for c in mcp.call_log if c["op"] == "read"]
    assert all(c["section_id"] != "ch1" for c in read_calls)
    ch2_calls = [c for c in read_calls if c["section_id"] == "ch2"]
    assert [(c["mode"], c["cursor"]) for c in ch2_calls] == [("cursor", "ch2-p2")]
    assert any(c["section_id"] == "ch3" for c in read_calls)

    final_cov = build_coverage_report(resumed)
    assert final_cov["completeness_status"] == "complete"
    assert final_cov["chapters_done"] == 3


def test_coverage_warnings_for_partial_missing_truncated_and_sequential_fallback(tmp_path: Path):
    """Coverage report and generated skill surface explicit warnings on partial/missing/fallback books."""
    mcp = MockMCPServer()
    partial_skill = tmp_path / "partial-skill"
    partial_work = tmp_path / "partial-work"

    partial_res = _run_mock_mode2_pipeline(
        mcp,
        query="Incomplete Diagnostics Handbook",
        skill_dir=partial_skill,
        workdir=partial_work,
        confirmation_reply="confirm",
    )
    cov = partial_res["coverage"]
    assert cov["completeness_status"] == "partial"
    assert cov["chapters_done"] == 1
    assert cov["chapters_incomplete"] == 1
    assert cov["chapters_failed"] == 1
    assert [s["section_id"] for s in cov["truncated_sections"]] == ["ch2"]
    assert [s["section_id"] for s in cov["missing_sections"]] == ["ch3"]
    assert any("ch2" in w and "truncated" in w.lower() for w in cov["warnings"])
    assert any("ch3" in w and "missing" in w.lower() for w in cov["warnings"])

    ch2_md = (partial_skill / "chapters" / "ch02-truncated-trace-chapter.md").read_text(encoding="utf-8")
    assert "Incomplete/Truncated Warning" in ch2_md
    skill_md = (partial_skill / "SKILL.md").read_text(encoding="utf-8")
    assert "`partial`" in skill_md
    assert "Truncated sections:" in skill_md
    assert "Missing sections:" in skill_md
    assert scan_tool.scan_generated_skill(partial_skill) == []

    # Sequential fallback when outline is unavailable
    seq_skill = tmp_path / "seq-skill"
    seq_work = tmp_path / "seq-work"
    seq_res = _run_mock_mode2_pipeline(
        mcp,
        query="Sequential Notes on Queues",
        skill_dir=seq_skill,
        workdir=seq_work,
        confirmation_reply="yes",
    )
    assert seq_res["session"]["outline_mode"] == "sequential_fallback"
    assert any("sequential fallback" in w.lower() for w in seq_res["coverage"]["warnings"])
    assert "Sequential fallback" in format_coverage_summary(seq_res["coverage"])
    assert scan_tool.scan_generated_skill(seq_skill) == []


def test_timeout_cancel_corrupt_cursor_and_inconsistent_details_handling(tmp_path: Path):
    """Failure injections (timeout, cancel, corrupt_cursor, cursor_loop, inconsistent_details) fail safely."""
    # 1. Timeout mid-run preserves earlier checkpointed chapters on disk
    mcp = MockMCPServer()
    workdir = tmp_path / "timeout-work"
    details = normalize_work_details(mcp.get_details("syn-arch-epub-2"))
    _, chapters = parse_outline_response(mcp.read("syn-arch-epub-2", mode="outline"))
    session = init_remote_session(
        details,
        provider="libgen-mcp",
        outline_mode="outline",
        chapters=chapters,
        confirmed_by_user=True,
    )
    ch1_res = read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch1"))
    update_chapter_progress(session, "ch1", progress=ch1_res)
    save_remote_session(session, workdir)

    mcp.set_failure("timeout", {"op": "read", "section_id": "ch2"})
    with pytest.raises(MockMCPTimeoutError):
        read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch2"))

    # Earlier checkpoint remains intact and valid on disk
    reloaded = load_remote_session(workdir)
    assert reloaded is not None
    assert [c["section_id"] for c in pending_chapters(reloaded)] == ["ch2", "ch3"]

    # 2. Cancel during search/read raises cleanly without creating files
    mcp.clear_failures()
    mcp.set_failure("cancel", "search")
    with pytest.raises(MockMCPCancelledError):
        mcp.search("Synthetic Systems Design")
    assert not (tmp_path / "full_text.txt").exists()

    # 3. Corrupt cursor (both injected error and unrecognized cursor token)
    mcp.clear_failures()
    corrupt_direct = read_section_from_pages(
        [mcp.read("syn-arch-epub-2", mode="cursor", section_id="ch2", cursor="tampered-cursor")]
    )
    assert corrupt_direct["status"] == "failed"
    assert "corrupt_cursor" in (corrupt_direct["error_reason"] or "")

    mcp.set_failure("corrupt_cursor", {"op": "read", "section_id": "ch2"})
    corrupt_injected = read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch2"))
    assert corrupt_injected["status"] == "failed"
    assert "corrupt_cursor" in (corrupt_injected["error_reason"] or "")

    # 4. Infinite cursor loop halts cleanly as incomplete
    mcp.clear_failures()
    mcp.set_failure("cursor_loop", {"op": "read", "section_id": "ch1"})
    loop_res = read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch1"))
    assert loop_res["status"] == "incomplete"
    assert "loop" in (loop_res["error_reason"] or "").lower()

    # 4b. Injected truncated & missing_chapter failure modes
    mcp.clear_failures()
    mcp.set_failure("truncated", {"op": "read", "section_id": "ch1"})
    trunc_res = read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch1"))
    assert trunc_res["status"] == "incomplete"
    assert trunc_res["truncated"] is True

    mcp.clear_failures()
    mcp.set_failure("missing_chapter", {"op": "read", "section_id": "ch1"})
    miss_res = read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch1"))
    assert miss_res["status"] == "failed"
    assert miss_res["missing"] is True

    # 5. Inconsistent details between search and get_details aborts before reading
    mcp.clear_failures()
    mcp.set_failure("inconsistent_details", {"op": "get_details", "item_id": "syn-arch-epub-2"})
    with pytest.raises(ValueError, match="Inconsistent metadata"):
        _run_mock_mode2_pipeline(
            mcp,
            query="Synthetic Systems Design",
            skill_dir=tmp_path / "mismatch-skill",
            workdir=tmp_path / "mismatch-work",
        )
    # Must fail before issuing any read() call
    assert not any(
        c["op"] == "read" and c.get("item_id") == "syn-arch-epub-2"
        for c in mcp.call_log[-2:]
    )
    assert json.loads((workdir / SESSION_FILENAME).read_text(encoding="utf-8"))["schema_version"] == 1
