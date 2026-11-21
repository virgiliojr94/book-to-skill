"""Offline MCP read-mode processors (outline, section, cursor) and sanitization."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from book_to_skill.sanitize import sanitize_extracted_text

SUPPORTED_READ_MODES = frozenset({"outline", "section", "cursor"})

_OUTLINE_LIST_KEYS = ("chapters", "outline", "sections", "toc", "items", "entries")
_OUTLINE_WRAPPER_KEYS = ("outline", "toc", "result", "data")
_SECTION_ID_KEYS = ("section_id", "id", "chapter_id", "href", "path", "node_id")
_TITLE_KEYS = ("title", "name", "heading", "label")
_INDEX_KEYS = ("index", "order", "number", "chapter_number")

__all__ = [
    "SUPPORTED_READ_MODES",
    "parse_outline_response",
    "process_section_page",
    "read_section_from_pages",
    "sanitize_remote_chunk",
]


def _sanitize_text_field(value: Any) -> str:
    """Convert a scalar metadata value to sanitized, stripped text."""
    if value is None or isinstance(value, bool):
        return ""
    cleaned, _ = sanitize_extracted_text(str(value))
    return cleaned.strip()


def _pick_first_non_empty(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-empty value found in ``mapping`` for ``keys``."""
    for key in keys:
        if key not in mapping:
            continue
        val = mapping[key]
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        return val
    return None


def _parse_positive_index(raw_value: Any, fallback: int) -> int:
    """Parse a 1-based integer index, returning ``fallback`` if absent or invalid."""
    if raw_value is None or isinstance(raw_value, bool):
        return fallback
    if isinstance(raw_value, int):
        return raw_value if raw_value >= 0 else fallback
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped.isdigit():
            return int(stripped)
    return fallback


def sanitize_remote_chunk(raw_text: str) -> dict[str, Any]:
    """Sanitize a remote MCP text chunk via :func:`sanitize_extracted_text`.

    Returns ``{"text": str, "removed_invisible_count": int, "empty": bool}``.
    """
    if raw_text is None:
        text_input = ""
    elif isinstance(raw_text, str):
        text_input = raw_text
    else:
        raise TypeError(f"raw_text must be str or None, got {type(raw_text).__name__}")

    cleaned, removed_count = sanitize_extracted_text(text_input)
    return {
        "text": cleaned,
        "removed_invisible_count": removed_count,
        "empty": not cleaned.strip(),
    }


def _extract_outline_entries(raw_outline: dict[str, Any]) -> list[Any] | None:
    """Locate the raw chapter/section list inside an MCP outline payload."""
    for key in _OUTLINE_LIST_KEYS:
        val = raw_outline.get(key)
        if isinstance(val, list):
            return val

    for wrapper_key in _OUTLINE_WRAPPER_KEYS:
        nested = raw_outline.get(wrapper_key)
        if isinstance(nested, dict):
            for key in _OUTLINE_LIST_KEYS:
                val = nested.get(key)
                if isinstance(val, list):
                    return val
    return None


def parse_outline_response(raw_outline: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Parse an MCP ``read(mode="outline")`` payload into normalized chapters.

    Returns ``("outline", chapters)`` when valid section IDs are present, or
    ``("sequential_fallback", [])`` when the outline is missing, empty, flat,
    marked unreliable, or lacks unique ``section_id`` values.
    """
    if not isinstance(raw_outline, dict) or not raw_outline:
        return "sequential_fallback", []

    if raw_outline.get("reliable") is False or raw_outline.get("unreliable") is True:
        return "sequential_fallback", []
    if raw_outline.get("outline_available") is False:
        return "sequential_fallback", []

    mode_hint = _sanitize_text_field(raw_outline.get("mode") or raw_outline.get("outline_mode")).lower()
    if mode_hint == "sequential_fallback":
        return "sequential_fallback", []

    status_hint = _sanitize_text_field(raw_outline.get("status")).lower()
    if status_hint in {"error", "failed", "unavailable", "missing", "unreliable"}:
        return "sequential_fallback", []
    if raw_outline.get("error"):
        return "sequential_fallback", []

    raw_entries = _extract_outline_entries(raw_outline)
    if not raw_entries:
        return "sequential_fallback", []

    chapters: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for pos, entry in enumerate(raw_entries, start=1):
        if not isinstance(entry, dict):
            return "sequential_fallback", []

        raw_index = _pick_first_non_empty(entry, _INDEX_KEYS)
        index = _parse_positive_index(raw_index, pos)

        raw_section_id = _pick_first_non_empty(entry, _SECTION_ID_KEYS)
        section_id = _sanitize_text_field(raw_section_id)
        if not section_id and raw_index is not None and not isinstance(raw_index, bool):
            section_id = str(index)
        if not section_id or section_id in seen_ids:
            return "sequential_fallback", []
        seen_ids.add(section_id)

        raw_title = _pick_first_non_empty(entry, _TITLE_KEYS)
        title = _sanitize_text_field(raw_title) or f"Section {pos}"

        chapters.append(
            {
                "index": index,
                "section_id": section_id,
                "title": title,
            }
        )

    return "outline", chapters


def _normalize_cursor(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    cleaned = _sanitize_text_field(value)
    return cleaned if cleaned else None


def process_section_page(
    raw_page: dict[str, Any],
    *,
    seen_cursors: set[str],
    max_cursors_per_section: int = 100,
) -> dict[str, Any]:
    """Sanitize and validate one MCP ``read(section|cursor)`` response page.

    Detects missing/error payloads, ``truncated`` responses, empty pages,
    repeated cursors (infinite cursor loops), and ``max_cursors_per_section``
    bounds. Mutates ``seen_cursors`` with newly observed cursors.
    """
    if not isinstance(seen_cursors, set):
        raise TypeError(f"seen_cursors must be a set, got {type(seen_cursors).__name__}")
    if isinstance(max_cursors_per_section, bool) or not isinstance(max_cursors_per_section, int):
        raise TypeError("max_cursors_per_section must be an int")

    if not isinstance(raw_page, dict):
        return {
            "text": "",
            "removed_invisible_count": 0,
            "empty": True,
            "truncated": False,
            "missing": True,
            "next_cursor": None,
            "has_more": False,
            "loop_detected": False,
            "cursor_limit_reached": False,
            "status": "failed",
            "error_reason": "Malformed page payload: expected dict.",
        }

    raw_status = _sanitize_text_field(raw_page.get("status")).lower()
    raw_error = _sanitize_text_field(raw_page.get("error") or raw_page.get("error_reason"))
    raw_reason = _sanitize_text_field(raw_page.get("reason"))
    unextractable = raw_page.get("extractable") is False
    missing_flag = (
        raw_page.get("missing") is True
        or raw_page.get("found") is False
        or raw_status in {"missing", "not_found"}
    )
    truncated_flag = raw_page.get("truncated") is True or raw_page.get("is_truncated") is True

    raw_text = raw_page.get("text")
    if raw_text is None:
        raw_text = raw_page.get("content")
    if raw_text is None:
        raw_text = raw_page.get("chunk")
    sanitized = sanitize_remote_chunk("" if raw_text is None else str(raw_text))

    explicit_next_cursor = _normalize_cursor(
        raw_page.get("next_cursor") or raw_page.get("nextCursor") or raw_page.get("cursor_next")
    )
    cursor_field = _normalize_cursor(raw_page.get("cursor"))
    # libgen-mcp returns {"has_more": true, "cursor": "<next-cursor>"} with no `next_cursor` key.
    if explicit_next_cursor is None and raw_page.get("has_more") is True and cursor_field is not None:
        current_cursor = _normalize_cursor(raw_page.get("current_cursor") or raw_page.get("page_cursor"))
        raw_next_cursor = cursor_field
    else:
        current_cursor = _normalize_cursor(
            raw_page.get("cursor") or raw_page.get("current_cursor") or raw_page.get("page_cursor")
        )
        raw_next_cursor = explicit_next_cursor

    if missing_flag:
        return {
            "text": sanitized["text"],
            "removed_invisible_count": sanitized["removed_invisible_count"],
            "empty": sanitized["empty"],
            "truncated": truncated_flag,
            "missing": True,
            "next_cursor": None,
            "has_more": False,
            "loop_detected": False,
            "cursor_limit_reached": False,
            "status": "failed",
            "error_reason": raw_error or raw_reason or "Section is missing or not found.",
        }

    if unextractable or raw_error or raw_status in {"error", "failed"}:
        return {
            "text": sanitized["text"],
            "removed_invisible_count": sanitized["removed_invisible_count"],
            "empty": sanitized["empty"],
            "truncated": truncated_flag,
            "missing": False,
            "next_cursor": None,
            "has_more": False,
            "loop_detected": False,
            "cursor_limit_reached": False,
            "status": "failed",
            "error_reason": raw_error or raw_reason or "Provider reported unextractable or failed content.",
        }

    if current_cursor is not None:
        seen_cursors.add(current_cursor)

    if raw_next_cursor is not None:
        if raw_next_cursor in seen_cursors or (
            current_cursor is not None and raw_next_cursor == current_cursor
        ):
            return {
                "text": sanitized["text"],
                "removed_invisible_count": sanitized["removed_invisible_count"],
                "empty": sanitized["empty"],
                "truncated": truncated_flag,
                "missing": False,
                "next_cursor": None,
                "has_more": False,
                "loop_detected": True,
                "cursor_limit_reached": False,
                "status": "incomplete",
                "error_reason": f"Infinite cursor loop detected for cursor {raw_next_cursor!r}.",
            }

        if max_cursors_per_section < 1 or len(seen_cursors) >= max_cursors_per_section:
            return {
                "text": sanitized["text"],
                "removed_invisible_count": sanitized["removed_invisible_count"],
                "empty": sanitized["empty"],
                "truncated": truncated_flag,
                "missing": False,
                "next_cursor": None,
                "has_more": False,
                "loop_detected": False,
                "cursor_limit_reached": True,
                "status": "incomplete",
                "error_reason": f"Cursor limit reached ({max_cursors_per_section} cursors per section).",
            }

        seen_cursors.add(raw_next_cursor)
        return {
            "text": sanitized["text"],
            "removed_invisible_count": sanitized["removed_invisible_count"],
            "empty": sanitized["empty"],
            "truncated": truncated_flag,
            "missing": False,
            "next_cursor": raw_next_cursor,
            "has_more": True,
            "loop_detected": False,
            "cursor_limit_reached": False,
            "status": "incomplete" if truncated_flag else "in_progress",
            "error_reason": "Section content was truncated by provider." if truncated_flag else None,
        }

    if truncated_flag:
        return {
            "text": sanitized["text"],
            "removed_invisible_count": sanitized["removed_invisible_count"],
            "empty": sanitized["empty"],
            "truncated": True,
            "missing": False,
            "next_cursor": None,
            "has_more": False,
            "loop_detected": False,
            "cursor_limit_reached": False,
            "status": "incomplete",
            "error_reason": "Section content was truncated by provider.",
        }

    if sanitized["empty"]:
        return {
            "text": sanitized["text"],
            "removed_invisible_count": sanitized["removed_invisible_count"],
            "empty": True,
            "truncated": False,
            "missing": False,
            "next_cursor": None,
            "has_more": False,
            "loop_detected": False,
            "cursor_limit_reached": False,
            "status": "incomplete",
            "error_reason": "Empty or unreadable section content.",
        }

    return {
        "text": sanitized["text"],
        "removed_invisible_count": sanitized["removed_invisible_count"],
        "empty": False,
        "truncated": False,
        "missing": False,
        "next_cursor": None,
        "has_more": False,
        "loop_detected": False,
        "cursor_limit_reached": False,
        "status": "done",
        "error_reason": None,
    }


def read_section_from_pages(
    pages: Iterable[dict[str, Any]],
    *,
    max_cursors_per_section: int = 100,
    max_total_requests: int = 1000,
    requests_used: int = 0,
    initial_seen_cursors: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Reduce paginated MCP section/cursor pages into sanitized text and status.

    Enforces ``max_cursors_per_section`` and ``max_total_requests``, stops on
    infinite cursor loops or missing/failed responses, and returns only
    sanitized text for immediate synthesis (callers discard it afterwards).
    """
    if isinstance(max_total_requests, bool) or not isinstance(max_total_requests, int) or max_total_requests < 0:
        raise ValueError("max_total_requests must be a non-negative int")
    if isinstance(requests_used, bool) or not isinstance(requests_used, int) or requests_used < 0:
        raise ValueError("requests_used must be a non-negative int")

    seen_cursors: set[str] = set(initial_seen_cursors or ())
    chunks: list[str] = []
    chunks_read = 0
    requests_made = 0
    total_requests = requests_used
    sanitized_removed_count = 0
    truncated = False
    missing = False
    next_cursor: str | None = None
    status = "incomplete"
    error_reason: str | None = None

    for raw_page in pages:
        if total_requests >= max_total_requests:
            status = "incomplete"
            error_reason = f"max_total_requests limit reached ({max_total_requests})."
            break

        requests_made += 1
        total_requests += 1

        page = process_section_page(
            raw_page,
            seen_cursors=seen_cursors,
            max_cursors_per_section=max_cursors_per_section,
        )
        sanitized_removed_count += page["removed_invisible_count"]

        if page["text"] and not page["empty"]:
            chunks.append(page["text"])
            chunks_read += 1

        if page["truncated"]:
            truncated = True
        if page["missing"]:
            missing = True

        next_cursor = page["next_cursor"]

        if page["status"] == "failed":
            status = "failed"
            error_reason = page["error_reason"]
            break

        if page["loop_detected"] or page["cursor_limit_reached"]:
            status = "incomplete"
            error_reason = page["error_reason"]
            break

        if not page["has_more"]:
            if truncated:
                status = "incomplete"
                error_reason = page["error_reason"] or "Section content was truncated by provider."
            elif chunks_read == 0:
                status = "incomplete"
                error_reason = page["error_reason"] or "Empty or unreadable section content."
            else:
                status = "done"
                error_reason = None
            break

        if total_requests >= max_total_requests:
            status = "incomplete"
            error_reason = f"max_total_requests limit reached ({max_total_requests})."
            break

        status = "incomplete" if truncated else "in_progress"
        error_reason = page["error_reason"]

    if requests_made == 0:
        if total_requests >= max_total_requests:
            status = "incomplete"
            error_reason = f"max_total_requests limit reached ({max_total_requests})."
        else:
            status = "incomplete"
            error_reason = "No pages returned for section."

    return {
        "text": "\n".join(chunks),
        "chunks": chunks,
        "status": status,
        "next_cursor": next_cursor,
        "chunks_read": chunks_read,
        "requests_made": requests_made,
        "total_requests": total_requests,
        "sanitized_removed_count": sanitized_removed_count,
        "truncated": truncated,
        "missing": missing,
        "error_reason": error_reason,
    }
