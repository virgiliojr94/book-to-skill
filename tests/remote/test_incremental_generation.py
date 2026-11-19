"""Tests for Mode 2 incremental skill generation, provenance, and security scans."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from book_to_skill.remote import (
    build_access_copyright_notice,
    build_coverage_report,
    build_remote_provenance,
    check_provider_allowed,
    format_candidate_selection_table,
    format_coverage_summary,
    group_duplicate_editions,
    init_remote_session,
    load_policy,
    load_remote_session,
    normalize_search_results,
    normalize_work_details,
    parse_outline_response,
    pending_chapters,
    read_section_from_pages,
    render_provenance_markdown,
    resolve_publish_visibility,
    save_remote_session,
    update_chapter_progress,
    verify_user_confirmation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_tool(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "tools" / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


scan_tool = _load_tool("scan_generated_skill", "scan_generated_skill.py")
validate_tool = _load_tool("validate_skill", "validate_skill.py")


def _run_synthetic_incremental_generation(
    tmp_path: Path,
    *,
    chapter_pages: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Execute the Mode 2 incremental pipeline on synthetic non-copyrighted payloads."""
    raw_search = [
        {
            "id": "syn-book-001",
            "title": "Synthetic Systems Field Guide",
            "authors": ["Ada Example", "Alan Sample"],
            "edition": "2nd",
            "year": 2025,
            "format": "epub",
            "language": "en",
            "isbn": ["9780000000001"],
            "source_name": "Synthetic Open Archive",
            "access_info": "synthetic-test-fixture",
            "license_info": "CC-BY-4.0",
        }
    ]
    candidates = normalize_search_results(raw_search, provider="libgen-mcp")
    grouped = group_duplicate_editions(candidates)
    table = format_candidate_selection_table(grouped)
    assert "Synthetic Systems Field Guide" in table

    selected = normalize_work_details(
        {
            "id": "syn-book-001",
            "title": "Synthetic Systems Field Guide",
            "authors": ["Ada Example", "Alan Sample"],
            "edition": "2nd",
            "year": 2025,
            "format": "epub",
            "language": "en",
            "isbn": ["9780000000001"],
            "doi": "10.5555/synthetic.001",
            "source_name": "Synthetic Open Archive",
            "access_info": "synthetic-test-fixture",
            "license_info": "CC-BY-4.0",
        },
        provider="libgen-mcp",
    )

    policy = load_policy({"require_explicit_confirmation": True})
    allowed, reason = check_provider_allowed("libgen-mcp", policy)
    assert allowed, reason

    notice = build_access_copyright_notice(selected, policy)
    assert "does not equal copyright-holder authorization" in notice.lower()
    assert verify_user_confirmation("yes, proceed", selected, policy) is True

    outline_mode, outline_chapters = parse_outline_response(
        {
            "outline": [
                {"index": 1, "section_id": "ch1", "title": "Feedback Loops"},
                {"index": 2, "section_id": "ch2", "title": "Boundary Guards"},
            ]
        }
    )
    assert outline_mode == "outline"

    workdir = tmp_path / "remote_workdir"
    skill_dir = tmp_path / "skills" / "example-systems-guide"
    chapters_dir = skill_dir / "chapters"
    chapters_dir.mkdir(parents=True)

    session = init_remote_session(
        work=selected,
        provider="libgen-mcp",
        outline_mode=outline_mode,
        chapters=outline_chapters,
        confirmed_by_user=True,
        session_id="syn-sess-001",
    )
    session_path = save_remote_session(session, workdir)

    chapter_files: list[Path] = []
    for ch in pending_chapters(session):
        sec_id = ch["section_id"]
        result = read_section_from_pages(chapter_pages[sec_id])

        # Synthesize immediately from sanitized text, then discard raw chunks.
        slug = ch["title"].lower().replace(" ", "-")
        ch_path = chapters_dir / f"ch{ch['index']:02d}-{slug}.md"
        warning_block = ""
        if result["status"] != "done" or result["truncated"]:
            warning_block = (
                f"> **Warning:** Incomplete/truncated section "
                f"({result['error_reason'] or 'partial content'}).\n\n"
            )
        synthesized_body = (
            f"# Chapter {ch['index']}: {ch['title']}\n\n"
            f"{warning_block}"
            f"## Core Idea\n\n"
            f"Use bounded checkpoints and sanitized boundaries when handling {ch['title'].lower()}.\n\n"
            f"## Key Takeaways\n\n"
            f"- Chunks synthesized: {result['chunks_read']}\n"
        )
        ch_path.write_text(synthesized_body, encoding="utf-8")
        chapter_files.append(ch_path)

        # Explicitly discard raw prose before updating checkpoint.
        del result["text"]
        del result["chunks"]

        session = update_chapter_progress(
            session,
            sec_id,
            status=result["status"],
            next_cursor=result["next_cursor"],
            chunks_read=result["chunks_read"],
            sanitized_removed_count=result["sanitized_removed_count"],
            truncated=result["truncated"],
            error_reason=result["error_reason"],
        )
        save_remote_session(session, workdir)

    (skill_dir / "glossary.md").write_text(
        "# Glossary\n\n"
        "**Boundary Guard** — Validation rule isolating untrusted inputs (Ch 2).\n"
        "**Feedback Loop** — Closed verification cycle keeping state accurate (Ch 1).\n",
        encoding="utf-8",
    )
    (skill_dir / "patterns.md").write_text(
        "# Patterns\n\n"
        "## Ephemeral Chapter Synthesis\n"
        "**When to use**: Reading remote works chapter by chapter.\n"
        "**How**: Sanitize chunks, write synthesized notes, discard raw fragments.\n"
        "**Trade-offs**: Avoids raw storage while keeping structured takeaways.\n",
        encoding="utf-8",
    )
    (skill_dir / "cheatsheet.md").write_text(
        "# Cheatsheet\n\n"
        "| Situation | Rule | Reason |\n"
        "|---|---|---|\n"
        "| Untrusted chunk | Sanitize before synthesis | Strips invisible controls |\n",
        encoding="utf-8",
    )

    coverage = build_coverage_report(session)
    provenance = build_remote_provenance(selected, session, policy, coverage=coverage)
    provenance_md = render_provenance_markdown(provenance)
    coverage_md = format_coverage_summary(coverage)
    assert resolve_publish_visibility("public domain", policy) == "private"

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: example-systems-guide\n"
        'description: "Knowledge base from Synthetic Systems Field Guide."\n'
        "---\n\n"
        "# Synthetic Systems Field Guide\n\n"
        "## Core Frameworks & Mental Models\n\n"
        "- **Ephemeral Synthesis**: Synthesize per chapter and discard raw fragments.\n\n"
        "## Chapter Index\n\n"
        "| # | Title | Key Frameworks |\n"
        "|---|---|---|\n"
        "| [ch01](chapters/ch01-feedback-loops.md) | Feedback Loops | Feedback Loop |\n"
        "| [ch02](chapters/ch02-boundary-guards.md) | Boundary Guards | Boundary Guard |\n\n"
        "## Supporting Files\n\n"
        "- [glossary.md](glossary.md) — key terms\n"
        "- [patterns.md](patterns.md) — design patterns\n"
        "- [cheatsheet.md](cheatsheet.md) — quick reference\n\n"
        "## Scope & Limits\n\n"
        "Synthesized notes only; no raw book text or full_text.txt is stored.\n\n"
        f"{provenance_md}\n",
        encoding="utf-8",
    )

    return {
        "skill_dir": skill_dir,
        "skill_md": skill_md,
        "workdir": workdir,
        "session_path": session_path,
        "chapter_files": chapter_files,
        "coverage": coverage,
        "coverage_md": coverage_md,
        "provenance": provenance,
    }


def test_remote_package_exports_all_public_apis():
    """book_to_skill.remote.__init__ cleanly exports all public symbols across PR 2-4."""
    remote = importlib.import_module("book_to_skill.remote")
    expected = {
        "normalize_search_results",
        "normalize_work_details",
        "group_duplicate_editions",
        "format_candidate_selection_table",
        "load_policy",
        "check_provider_allowed",
        "build_access_copyright_notice",
        "verify_user_confirmation",
        "resolve_publish_visibility",
        "sanitize_remote_chunk",
        "parse_outline_response",
        "process_section_page",
        "read_section_from_pages",
        "init_remote_session",
        "save_remote_session",
        "load_remote_session",
        "update_chapter_progress",
        "pending_chapters",
        "build_coverage_report",
        "format_coverage_summary",
        "build_remote_provenance",
        "render_provenance_markdown",
    }
    assert expected.issubset(set(remote.__all__))
    for name in expected:
        assert hasattr(remote, name), f"missing export in book_to_skill.remote: {name}"


def test_incremental_mode2_produces_standard_skill_without_full_text(tmp_path):
    """Mode 2 produces the standard skill layout, zero full_text.txt, and passes scan + validate."""
    sentinel_prose = "UNIQUE_RAW_PROSE_TOKEN_NEVER_PERSISTED"
    result = _run_synthetic_incremental_generation(
        tmp_path,
        chapter_pages={
            "ch1": [
                {
                    "text": f"Synthetic chunk one\u200b {sentinel_prose}.",
                    "next_cursor": "c1-p2",
                },
                {
                    "text": "Synthetic chunk two.",
                    "next_cursor": None,
                },
            ],
            "ch2": [
                {
                    "text": "Boundary guards isolate untrusted inputs.",
                    "next_cursor": None,
                }
            ],
        },
    )

    skill_dir: Path = result["skill_dir"]
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "glossary.md").is_file()
    assert (skill_dir / "patterns.md").is_file()
    assert (skill_dir / "cheatsheet.md").is_file()
    assert sorted(p.name for p in (skill_dir / "chapters").glob("*.md")) == [
        "ch01-feedback-loops.md",
        "ch02-boundary-guards.md",
    ]

    # Zero full_text.txt anywhere in skill_dir or workdir
    assert list(tmp_path.rglob("full_text.txt")) == []

    # Checkpoint session & provenance store zero raw prose
    persisted_session = json.loads(result["session_path"].read_text(encoding="utf-8"))
    assert persisted_session["chapters"][0]["sanitized_removed_count"] >= 1
    assert sentinel_prose not in json.dumps(persisted_session)
    assert sentinel_prose not in json.dumps(result["provenance"])
    assert load_remote_session(result["workdir"]) is not None

    skill_text = result["skill_md"].read_text(encoding="utf-8")
    assert "## Scope & Limits" in skill_text
    assert "### Remote Source & Provenance" in skill_text
    assert "incremental_ephemeral_no_full_text" in skill_text
    assert "`complete`" in skill_text

    # Advisory security scan and 6-lens skill validation pass
    assert scan_tool.scan_generated_skill(skill_dir) == []
    assert scan_tool.main([str(skill_dir)]) == 0
    for lens in sorted(validate_tool.LENSES.keys()):
        errors, _warns = validate_tool.audit(str(result["skill_md"]), lens=lens)
        assert errors == [], f"validate_skill failed on generated SKILL.md ({lens}): {errors}"


def test_incremental_mode2_partial_truncation_surfaces_coverage_warning(tmp_path):
    """Truncated remote chapters produce explicit warnings in Scope & Limits and pass scans."""
    result = _run_synthetic_incremental_generation(
        tmp_path,
        chapter_pages={
            "ch1": [{"text": "Complete chapter one content.", "next_cursor": None}],
            "ch2": [
                {
                    "text": "Partial chapter two content.",
                    "truncated": True,
                    "next_cursor": None,
                }
            ],
        },
    )

    assert result["coverage"]["completeness_status"] == "partial"
    assert len(result["coverage"]["truncated_sections"]) == 1
    assert result["coverage"]["warnings"]

    skill_text = result["skill_md"].read_text(encoding="utf-8")
    assert "`partial`" in skill_text
    assert "Truncated sections" in skill_text

    ch2_text = (result["skill_dir"] / "chapters" / "ch02-boundary-guards.md").read_text(
        encoding="utf-8"
    )
    assert "Incomplete/truncated section" in ch2_text
    assert list(tmp_path.rglob("full_text.txt")) == []
    assert scan_tool.scan_generated_skill(result["skill_dir"]) == []
    for lens in sorted(validate_tool.LENSES.keys()):
        errors, _ = validate_tool.audit(str(result["skill_md"]), lens=lens)
        assert errors == []
