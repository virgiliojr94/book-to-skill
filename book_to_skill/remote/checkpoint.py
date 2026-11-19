"""Secure, prose-free session checkpoint persistence for remote MCP reading."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from book_to_skill.sanitize import sanitize_extracted_text

SCHEMA_VERSION = 1
SESSION_FILENAME = "remote_session.json"
VALID_OUTLINE_MODES = frozenset({"outline", "sequential_fallback"})
VALID_CHAPTER_STATUSES = frozenset({"pending", "in_progress", "done", "incomplete", "failed"})
DEFAULT_LIMITS: dict[str, int] = {
    "max_cursors_per_section": 100,
    "max_total_requests": 1000,
}
FORBIDDEN_PROSE_KEYS = frozenset(
    {
        "text",
        "raw_text",
        "content",
        "raw_content",
        "body",
        "full_text",
        "chunks",
        "pages",
        "excerpt",
        "markdown",
        "html",
    }
)

_WORK_REQUIRED_KEYS = ("item_id", "title", "authors", "edition", "identifiers")
_WORK_OPTIONAL_METADATA_KEYS = (
    "provider",
    "year",
    "format",
    "language",
    "source_name",
    "access_info",
    "license_info",
    "dedup_key",
)

_UNSET: Any = object()

__all__ = [
    "DEFAULT_LIMITS",
    "FORBIDDEN_PROSE_KEYS",
    "SCHEMA_VERSION",
    "SESSION_FILENAME",
    "VALID_CHAPTER_STATUSES",
    "VALID_OUTLINE_MODES",
    "init_remote_session",
    "load_remote_session",
    "pending_chapters",
    "save_remote_session",
    "update_chapter_progress",
]


def _sanitize_str(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    cleaned, _ = sanitize_extracted_text(str(value))
    return cleaned.strip()


def _sanitize_optional_str(value: Any) -> str | None:
    cleaned = _sanitize_str(value)
    return cleaned if cleaned else None


def _normalize_identifiers(raw_identifiers: Any) -> dict[str, Any]:
    if not isinstance(raw_identifiers, dict):
        return {}
    result: dict[str, Any] = {}
    if "isbn" in raw_identifiers:
        raw_isbn = raw_identifiers["isbn"]
        if isinstance(raw_isbn, (list, tuple)):
            result["isbn"] = [_sanitize_str(item) for item in raw_isbn if _sanitize_str(item)]
        elif _sanitize_optional_str(raw_isbn):
            result["isbn"] = [_sanitize_str(raw_isbn)]
        else:
            result["isbn"] = []
    if "doi" in raw_identifiers:
        result["doi"] = _sanitize_optional_str(raw_identifiers["doi"])
    return result


def _normalize_work_metadata(work: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(work, dict):
        raise ValueError(f"work must be a dict, got {type(work).__name__}")

    raw_authors = work.get("authors")
    authors: list[str]
    if isinstance(raw_authors, (list, tuple)):
        authors = [_sanitize_str(a) for a in raw_authors if _sanitize_str(a)]
    elif isinstance(raw_authors, str) and _sanitize_str(raw_authors):
        authors = [_sanitize_str(raw_authors)]
    else:
        authors = []

    normalized: dict[str, Any] = {
        "item_id": _sanitize_str(work.get("item_id")),
        "title": _sanitize_str(work.get("title")),
        "authors": authors,
        "edition": _sanitize_optional_str(work.get("edition")),
        "identifiers": _normalize_identifiers(work.get("identifiers")),
    }

    for key in _WORK_OPTIONAL_METADATA_KEYS:
        if key not in work:
            continue
        val = work[key]
        if key == "year":
            if val is None or (isinstance(val, int) and not isinstance(val, bool)):
                normalized["year"] = val
        elif isinstance(val, str):
            normalized[key] = _sanitize_optional_str(val)
        elif val is None:
            normalized[key] = None

    return normalized


def _normalize_limits(limits: dict[str, Any] | None) -> dict[str, int]:
    merged = dict(DEFAULT_LIMITS)
    if limits is None:
        return merged
    if not isinstance(limits, dict):
        raise ValueError(f"limits must be a dict or None, got {type(limits).__name__}")

    for key in ("max_cursors_per_section", "max_total_requests"):
        if key in limits:
            val = limits[key]
            if isinstance(val, bool) or not isinstance(val, int) or val < 1:
                raise ValueError(f"limits[{key!r}] must be a positive integer, got {val!r}")
            merged[key] = val
    return merged


def _normalize_chapter_entry(raw_chapter: dict[str, Any], default_index: int) -> dict[str, Any]:
    if not isinstance(raw_chapter, dict):
        raise ValueError(f"Chapter entry must be a dict, got {type(raw_chapter).__name__}")

    raw_index = raw_chapter.get("index", default_index)
    if isinstance(raw_index, bool) or not isinstance(raw_index, int) or raw_index < 0:
        raise ValueError(f"Chapter index must be a non-negative int, got {raw_index!r}")

    section_id = _sanitize_str(raw_chapter.get("section_id"))
    if not section_id:
        raise ValueError("Chapter entry must include a non-empty 'section_id'")

    title = _sanitize_str(raw_chapter.get("title")) or f"Section {raw_index}"

    status = raw_chapter.get("status", "pending")
    if not isinstance(status, str) or status not in VALID_CHAPTER_STATUSES:
        raise ValueError(f"Invalid chapter status {status!r}; expected one of {sorted(VALID_CHAPTER_STATUSES)}")

    next_cursor = _sanitize_optional_str(raw_chapter.get("next_cursor"))

    chunks_read = raw_chapter.get("chunks_read", 0)
    if isinstance(chunks_read, bool) or not isinstance(chunks_read, int) or chunks_read < 0:
        raise ValueError(f"chunks_read must be a non-negative int, got {chunks_read!r}")

    sanitized_removed_count = raw_chapter.get("sanitized_removed_count", 0)
    if (
        isinstance(sanitized_removed_count, bool)
        or not isinstance(sanitized_removed_count, int)
        or sanitized_removed_count < 0
    ):
        raise ValueError(
            f"sanitized_removed_count must be a non-negative int, got {sanitized_removed_count!r}"
        )

    truncated = raw_chapter.get("truncated", False)
    if not isinstance(truncated, bool):
        raise ValueError(f"truncated must be a bool, got {type(truncated).__name__}")

    error_reason = _sanitize_optional_str(raw_chapter.get("error_reason"))

    return {
        "index": raw_index,
        "section_id": section_id,
        "title": title,
        "status": status,
        "next_cursor": next_cursor,
        "chunks_read": chunks_read,
        "sanitized_removed_count": sanitized_removed_count,
        "truncated": truncated,
        "error_reason": error_reason,
    }


def _assert_no_raw_prose(value: Any, path: str = "session") -> None:
    """Assert that no forbidden raw prose keys exist anywhere in ``value``."""
    if isinstance(value, dict):
        for key, child in value.items():
            key_norm = str(key).strip().casefold()
            if key_norm in FORBIDDEN_PROSE_KEYS:
                raise ValueError(
                    f"Refusing to persist raw prose key {key!r} at {path}.{key} in {SESSION_FILENAME}"
                )
            _assert_no_raw_prose(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            _assert_no_raw_prose(item, f"{path}[{idx}]")


def _validate_session_structure(session: dict[str, Any]) -> None:
    if not isinstance(session, dict):
        raise ValueError(f"session must be a dict, got {type(session).__name__}")

    schema_version = session.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported or missing remote_session schema_version: {schema_version!r} "
            f"(expected {SCHEMA_VERSION})"
        )

    chapters = session.get("chapters")
    if not isinstance(chapters, list):
        raise ValueError("session['chapters'] must be a list")
    for idx, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            raise ValueError(f"session['chapters'][{idx}] must be a dict")

    _assert_no_raw_prose(session)


def _prepare_secure_workdir(workdir: Path) -> None:
    """Create or verify ``workdir`` with 0o700 permissions and no symlinks."""
    if workdir.is_symlink():
        raise ValueError(f"Refusing to use {workdir}: it is a symbolic link, not a real directory.")

    if workdir.exists():
        if not workdir.is_dir():
            raise ValueError(f"Refusing to use {workdir}: it exists and is not a directory.")
        if hasattr(os, "getuid"):
            owner_uid = workdir.stat().st_uid
            if owner_uid != os.getuid():
                raise ValueError(
                    f"Refusing to use {workdir}: it is owned by a different user (uid {owner_uid})."
                )
            os.chmod(workdir, 0o700)
    else:
        workdir.mkdir(parents=True, mode=0o700)
        if hasattr(os, "getuid"):
            os.chmod(workdir, 0o700)


def init_remote_session(
    work: dict[str, Any],
    provider: str,
    outline_mode: str,
    chapters: list[dict[str, Any]],
    *,
    confirmed_by_user: bool,
    session_id: str | None = None,
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Initialize a Contract C ``remote_session.json`` state dict with zero raw prose."""
    if not isinstance(provider, str) or not _sanitize_str(provider):
        raise ValueError("provider must be a non-empty string")
    if not isinstance(outline_mode, str) or outline_mode not in VALID_OUTLINE_MODES:
        raise ValueError(
            f"outline_mode must be one of {sorted(VALID_OUTLINE_MODES)}, got {outline_mode!r}"
        )
    if not isinstance(confirmed_by_user, bool):
        raise ValueError(f"confirmed_by_user must be a bool, got {type(confirmed_by_user).__name__}")
    if not isinstance(chapters, list):
        raise ValueError(f"chapters must be a list, got {type(chapters).__name__}")

    resolved_session_id = _sanitize_optional_str(session_id) or uuid.uuid4().hex
    normalized_work = _normalize_work_metadata(work)
    normalized_limits = _normalize_limits(limits)
    normalized_chapters = [
        _normalize_chapter_entry(ch, idx) for idx, ch in enumerate(chapters, start=1)
    ]

    session = {
        "schema_version": SCHEMA_VERSION,
        "session_id": resolved_session_id,
        "provider": _sanitize_str(provider),
        "work": normalized_work,
        "confirmed_by_user": confirmed_by_user,
        "outline_mode": outline_mode,
        "limits": normalized_limits,
        "chapters": normalized_chapters,
    }
    _assert_no_raw_prose(session)
    return session


def save_remote_session(session: dict[str, Any], workdir: Path | str) -> Path:
    """Atomically persist ``remote_session.json`` under a private 0o700 ``workdir``."""
    _validate_session_structure(session)

    target_dir = Path(workdir)
    _prepare_secure_workdir(target_dir)

    destination = target_dir / SESSION_FILENAME
    if destination.is_symlink():
        raise ValueError(f"Refusing to write {destination}: it is a symbolic link.")
    if destination.exists() and not destination.is_file():
        raise ValueError(f"Refusing to write {destination}: target exists and is not a regular file.")

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target_dir,
            prefix=".remote_session-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(session, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        if hasattr(os, "getuid"):
            os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise

    return destination


def load_remote_session(workdir: Path | str) -> dict[str, Any] | None:
    """Load and validate ``remote_session.json`` from ``workdir``, rejecting symlinks."""
    target_dir = Path(workdir)
    if target_dir.is_symlink():
        raise ValueError(f"Refusing to read from {target_dir}: it is a symbolic link.")
    if not target_dir.exists():
        return None
    if not target_dir.is_dir():
        raise ValueError(f"Refusing to read from {target_dir}: it is not a directory.")
    if hasattr(os, "getuid"):
        owner_uid = target_dir.stat().st_uid
        if owner_uid != os.getuid():
            raise ValueError(
                f"Refusing to read from {target_dir}: it is owned by a different user (uid {owner_uid})."
            )

    session_path = target_dir / SESSION_FILENAME
    if session_path.is_symlink():
        raise ValueError(f"Refusing to read {session_path}: it is a symbolic link.")
    if not session_path.exists():
        return None
    if not session_path.is_file():
        raise ValueError(f"Refusing to read {session_path}: it is not a regular file.")

    try:
        raw_text = session_path.read_text(encoding="utf-8")
        loaded = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load valid JSON from {session_path}: {exc}") from exc

    _validate_session_structure(loaded)
    return loaded


def update_chapter_progress(
    session: dict[str, Any],
    section_id: str,
    *,
    status: str | None = None,
    next_cursor: str | None = _UNSET,
    chunks_read: int | None = None,
    sanitized_removed_count: int | None = None,
    truncated: bool | None = None,
    error_reason: str | None = _UNSET,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update checkpoint metadata for a single chapter without storing raw prose."""
    _validate_session_structure(session)
    if not isinstance(section_id, str) or not section_id.strip():
        raise ValueError("section_id must be a non-empty string")

    target_chapter: dict[str, Any] | None = None
    for ch in session["chapters"]:
        if ch.get("section_id") == section_id:
            target_chapter = ch
            break
    if target_chapter is None:
        raise ValueError(f"Chapter with section_id {section_id!r} not found in session")

    if progress is not None:
        if not isinstance(progress, dict):
            raise ValueError(f"progress must be a dict or None, got {type(progress).__name__}")
        if status is None and "status" in progress:
            status = progress["status"]
        if next_cursor is _UNSET and "next_cursor" in progress:
            next_cursor = progress["next_cursor"]
        if chunks_read is None and "chunks_read" in progress:
            chunks_read = progress["chunks_read"]
        if sanitized_removed_count is None:
            if "sanitized_removed_count" in progress:
                sanitized_removed_count = progress["sanitized_removed_count"]
            elif "removed_invisible_count" in progress:
                sanitized_removed_count = progress["removed_invisible_count"]
        if truncated is None and "truncated" in progress:
            truncated = progress["truncated"]
        if error_reason is _UNSET and "error_reason" in progress:
            error_reason = progress["error_reason"]

    if status is not None:
        if not isinstance(status, str) or status not in VALID_CHAPTER_STATUSES:
            raise ValueError(
                f"Invalid chapter status {status!r}; expected one of {sorted(VALID_CHAPTER_STATUSES)}"
            )
        target_chapter["status"] = status

    if next_cursor is not _UNSET:
        target_chapter["next_cursor"] = _sanitize_optional_str(next_cursor)

    if chunks_read is not None:
        if isinstance(chunks_read, bool) or not isinstance(chunks_read, int) or chunks_read < 0:
            raise ValueError(f"chunks_read must be a non-negative int, got {chunks_read!r}")
        target_chapter["chunks_read"] = chunks_read

    if sanitized_removed_count is not None:
        if (
            isinstance(sanitized_removed_count, bool)
            or not isinstance(sanitized_removed_count, int)
            or sanitized_removed_count < 0
        ):
            raise ValueError(
                f"sanitized_removed_count must be a non-negative int, got {sanitized_removed_count!r}"
            )
        target_chapter["sanitized_removed_count"] = sanitized_removed_count

    if truncated is not None:
        if not isinstance(truncated, bool):
            raise ValueError(f"truncated must be a bool, got {type(truncated).__name__}")
        target_chapter["truncated"] = truncated

    if error_reason is not _UNSET:
        target_chapter["error_reason"] = _sanitize_optional_str(error_reason)

    return session


def pending_chapters(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Return non-done chapters in order for resume or reporting.

    Skips chapters with ``status == "done"`` and preserves ``"pending"``,
    ``"in_progress"``, ``"incomplete"``, and ``"failed"`` chapters along with
    their saved ``next_cursor`` and ``error_reason``.
    """
    _validate_session_structure(session)
    return [dict(ch) for ch in session["chapters"] if ch.get("status") != "done"]
