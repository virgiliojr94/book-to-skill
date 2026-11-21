"""Offline coverage reporting for incremental MCP reading sessions (Contract D)."""

from __future__ import annotations

import re
from typing import Any

from book_to_skill.sanitize import sanitize_extracted_text

COVERAGE_REPORT_KEYS = (
    "chapters_total",
    "chapters_done",
    "chapters_incomplete",
    "chapters_failed",
    "missing_sections",
    "truncated_sections",
    "completeness_status",
    "warnings",
)

__all__ = [
    "COVERAGE_REPORT_KEYS",
    "build_coverage_report",
    "format_coverage_summary",
]


def _clean_text(value: Any) -> str:
    """Normalize arbitrary scalar metadata into single-line sanitized text."""
    if value is None or isinstance(value, bool):
        return ""
    sanitized, _ = sanitize_extracted_text(str(value))
    return re.sub(r"\s+", " ", sanitized).strip()


def _clean_optional_text(value: Any) -> str | None:
    """Return normalized text or None when empty."""
    cleaned = _clean_text(value)
    return cleaned if cleaned else None


def _non_negative_int(value: Any, default: int = 0) -> int:
    """Coerce an integer value safely without accepting booleans."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value >= 0:
        return value
    return default


def _section_ref(
    *,
    index: int | None,
    section_id: str,
    title: str,
    status: str,
    reason: str | None,
) -> dict[str, Any]:
    """Build a prose-free section reference entry for missing/truncated lists."""
    return {
        "index": index,
        "section_id": section_id,
        "title": title,
        "status": status,
        "reason": reason,
    }


def _format_section_label(section_id: str, title: str) -> str:
    if title and title != section_id:
        return f"{section_id} ({title})"
    return section_id


def build_coverage_report(session: dict[str, Any]) -> dict[str, Any]:
    """Compute a deterministic Contract D coverage report from a Contract C session dict."""
    if not isinstance(session, dict):
        raise ValueError(f"session must be a dict, got {type(session).__name__}")

    raw_chapters = session.get("chapters")
    if raw_chapters is None:
        chapters: list[Any] = []
    elif isinstance(raw_chapters, list):
        chapters = raw_chapters
    else:
        raise ValueError(
            f"session['chapters'] must be a list, got {type(raw_chapters).__name__}"
        )

    outline_mode = _clean_text(session.get("outline_mode")).lower() or "outline"

    chapters_total = len(chapters)
    chapters_done = 0
    chapters_incomplete = 0
    chapters_failed = 0
    total_chunks_read = 0
    missing_sections: list[dict[str, Any]] = []
    truncated_sections: list[dict[str, Any]] = []
    warnings: list[str] = []

    if outline_mode == "sequential_fallback":
        warnings.append(
            "Sequential fallback mode was used because a structured outline was unavailable; "
            "chapter boundaries are inferred rather than outline-verified."
        )

    if chapters_total == 0:
        warnings.append("No chapters or sections were recorded in the remote reading session.")

    for pos, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            raise ValueError(
                f"Each entry in session['chapters'] must be a dict, got {type(chapter).__name__}"
            )

        raw_index = chapter.get("index")
        index = raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) else pos
        section_id = _clean_text(chapter.get("section_id")) or f"ch{index}"
        title = _clean_text(chapter.get("title")) or section_id
        status = _clean_text(chapter.get("status")).lower() or "pending"
        truncated = bool(chapter.get("truncated", False))
        chunks_read = _non_negative_int(chapter.get("chunks_read"), default=0)
        error_reason = _clean_optional_text(chapter.get("error_reason"))
        total_chunks_read += chunks_read
        label = _format_section_label(section_id, title)

        if status == "done" and not truncated:
            chapters_done += 1
            continue

        if status == "done" and truncated:
            chapters_incomplete += 1
            reason = error_reason or "section marked done with truncated=True"
            truncated_sections.append(
                _section_ref(
                    index=index,
                    section_id=section_id,
                    title=title,
                    status=status,
                    reason=reason,
                )
            )
            warnings.append(
                f"Section '{label}' was truncated ({reason}); synthesis may omit trailing content."
            )
            continue

        if status == "failed":
            chapters_failed += 1
            reason = error_reason or "chapter read failed"
            missing_sections.append(
                _section_ref(
                    index=index,
                    section_id=section_id,
                    title=title,
                    status=status,
                    reason=reason,
                )
            )
            if truncated:
                truncated_sections.append(
                    _section_ref(
                        index=index,
                        section_id=section_id,
                        title=title,
                        status=status,
                        reason=reason,
                    )
                )
                warnings.append(
                    f"Section '{label}' failed after truncation ({reason}) and is missing from the skill."
                )
            else:
                warnings.append(
                    f"Section '{label}' failed ({reason}) and is missing from the skill."
                )
            continue

        # Handles "incomplete", "pending", "in_progress", or any non-terminal status.
        chapters_incomplete += 1
        is_missing = (status == "pending") or (chunks_read == 0 and not truncated)

        if truncated:
            reason = error_reason or "section truncated before completion"
            truncated_sections.append(
                _section_ref(
                    index=index,
                    section_id=section_id,
                    title=title,
                    status=status,
                    reason=reason,
                )
            )
            if is_missing:
                missing_sections.append(
                    _section_ref(
                        index=index,
                        section_id=section_id,
                        title=title,
                        status=status,
                        reason=reason,
                    )
                )
                warnings.append(
                    f"Section '{label}' was truncated with 0 chunks read ({reason}) and is missing."
                )
            else:
                warnings.append(
                    f"Section '{label}' is incomplete and truncated ({reason}); "
                    "synthesis may omit trailing content."
                )
        elif is_missing:
            reason = error_reason or f"section remained '{status}' with 0 chunks read"
            missing_sections.append(
                _section_ref(
                    index=index,
                    section_id=section_id,
                    title=title,
                    status=status,
                    reason=reason,
                )
            )
            warnings.append(f"Section '{label}' is missing ({reason}).")
        else:
            reason = error_reason or f"section stopped in '{status}' state before completion"
            warnings.append(f"Section '{label}' is incomplete ({reason}).")

    if chapters_total == 0:
        completeness_status = "degraded"
    elif (
        chapters_done == chapters_total
        and chapters_incomplete == 0
        and chapters_failed == 0
        and not missing_sections
        and not truncated_sections
    ):
        completeness_status = "complete"
    elif chapters_done == 0 and (chapters_failed > 0 or total_chunks_read == 0):
        completeness_status = "degraded"
    elif chapters_failed > chapters_done:
        completeness_status = "degraded"
    else:
        completeness_status = "partial"

    return {
        "chapters_total": chapters_total,
        "chapters_done": chapters_done,
        "chapters_incomplete": chapters_incomplete,
        "chapters_failed": chapters_failed,
        "missing_sections": missing_sections,
        "truncated_sections": truncated_sections,
        "completeness_status": completeness_status,
        "warnings": warnings,
    }


def _format_section_item(entry: Any) -> str:
    if isinstance(entry, dict):
        section_id = _clean_text(entry.get("section_id")) or "unknown"
        title = _clean_text(entry.get("title"))
        reason = _clean_optional_text(entry.get("reason"))
        label = _format_section_label(section_id, title)
        return f"{label} ({reason})" if reason else label
    cleaned = _clean_text(entry)
    return cleaned or "unknown"


def format_coverage_summary(report: dict[str, Any]) -> str:
    """Render a concise coverage summary block for Step 10 and SKILL.md Scope & Limits."""
    if not isinstance(report, dict):
        raise ValueError(f"report must be a dict, got {type(report).__name__}")

    status = _clean_text(report.get("completeness_status")).lower() or "degraded"
    total = _non_negative_int(report.get("chapters_total"), default=0)
    done = _non_negative_int(report.get("chapters_done"), default=0)
    incomplete = _non_negative_int(report.get("chapters_incomplete"), default=0)
    failed = _non_negative_int(report.get("chapters_failed"), default=0)

    counts_detail = f"{done}/{total} chapters done"
    if incomplete or failed:
        counts_detail += f", {incomplete} incomplete, {failed} failed"

    lines = [f"- **Coverage status:** `{status}` ({counts_detail})"]

    missing = report.get("missing_sections") or []
    if isinstance(missing, list) and missing:
        rendered_missing = "; ".join(_format_section_item(item) for item in missing)
        lines.append(f"- **Missing sections:** {rendered_missing}")

    truncated = report.get("truncated_sections") or []
    if isinstance(truncated, list) and truncated:
        rendered_truncated = "; ".join(_format_section_item(item) for item in truncated)
        lines.append(f"- **Truncated sections:** {rendered_truncated}")

    raw_warnings = report.get("warnings") or []
    if isinstance(raw_warnings, list):
        cleaned_warnings = [_clean_text(w) for w in raw_warnings if _clean_text(w)]
        if cleaned_warnings:
            lines.append("- **Coverage warnings:**")
            for warning in cleaned_warnings:
                lines.append(f"  - {warning}")

    return "\n".join(lines)
