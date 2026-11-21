"""Offline, prose-free provenance metadata builder and Markdown renderer (Contract D)."""

from __future__ import annotations

import re
from typing import Any

from book_to_skill.remote.coverage import (
    COVERAGE_REPORT_KEYS,
    build_coverage_report,
    format_coverage_summary,
)
from book_to_skill.remote.policy import resolve_publish_visibility
from book_to_skill.sanitize import sanitize_extracted_text

STORAGE_MODE = "incremental_ephemeral_no_full_text"

FORBIDDEN_PROSE_KEYS = frozenset(
    {
        "text",
        "raw_text",
        "content",
        "body",
        "excerpt",
        "excerpts",
        "chunk",
        "chunks",
        "full_text",
        "raw_content",
        "page_text",
        "prose",
        "snippet",
        "snippets",
        "pages",
        "raw_pages",
        "chapter_text",
    }
)

__all__ = [
    "FORBIDDEN_PROSE_KEYS",
    "STORAGE_MODE",
    "build_remote_provenance",
    "render_provenance_markdown",
]


def _clean_text(value: Any) -> str:
    """Normalize a scalar value into single-line sanitized text."""
    if value is None or isinstance(value, bool):
        return ""
    sanitized, _ = sanitize_extracted_text(str(value))
    return re.sub(r"\s+", " ", sanitized).strip()


def _clean_optional_text(value: Any) -> str | None:
    """Normalize optional metadata text, returning None when absent or empty."""
    cleaned = _clean_text(value)
    return cleaned if cleaned else None


def _normalize_authors(raw_authors: Any) -> list[str]:
    """Normalize and deduplicate author names into a sanitized list."""
    if raw_authors is None:
        return []
    if isinstance(raw_authors, str):
        items: list[Any] = [raw_authors]
    elif isinstance(raw_authors, (list, tuple)):
        items = list(raw_authors)
    else:
        return []

    authors: list[str] = []
    seen: set[str] = set()
    for entry in items:
        if isinstance(entry, dict):
            name = _clean_text(entry.get("name") or entry.get("full_name") or entry.get("author"))
        else:
            name = _clean_text(entry)
        if not name:
            continue
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            authors.append(name)
    return authors


def _normalize_year(value: Any) -> int | None:
    """Extract an integer publication year if valid, else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 2999 else None
    text = _clean_text(value)
    if text.isdigit():
        year_int = int(text)
        return year_int if 1 <= year_int <= 2999 else None
    return None


def _normalize_identifiers(primary: Any, fallback: Any) -> dict[str, Any]:
    """Normalize ISBN list and DOI string from candidate or session work metadata."""
    isbns: list[str] = []
    seen_isbns: set[str] = set()
    doi: str | None = None

    for source in (primary, fallback):
        if not isinstance(source, dict):
            continue
        raw_isbn = source.get("isbn")
        if isinstance(raw_isbn, (list, tuple)):
            isbn_items = raw_isbn
        elif raw_isbn is not None:
            isbn_items = [raw_isbn]
        else:
            isbn_items = []
        for item in isbn_items:
            cleaned = _clean_text(item)
            if cleaned and cleaned not in seen_isbns:
                seen_isbns.add(cleaned)
                isbns.append(cleaned)
        if doi is None:
            doi = _clean_optional_text(source.get("doi"))

    return {"isbn": isbns, "doi": doi}


def _scrub_section_entries(entries: Any) -> list[Any]:
    """Sanitize section entries while stripping any forbidden prose keys."""
    if not isinstance(entries, list):
        return []
    scrubbed: list[Any] = []
    for entry in entries:
        if isinstance(entry, dict):
            item: dict[str, Any] = {}
            for key in ("index", "section_id", "title", "status", "reason"):
                if key in entry:
                    val = entry[key]
                    if key == "index":
                        item[key] = val if isinstance(val, int) and not isinstance(val, bool) else None
                    elif key == "reason":
                        item[key] = _clean_optional_text(val)
                    else:
                        item[key] = _clean_text(val)
            scrubbed.append(item)
        else:
            cleaned = _clean_text(entry)
            if cleaned:
                scrubbed.append(cleaned)
    return scrubbed


def _sanitize_coverage_payload(coverage: dict[str, Any]) -> dict[str, Any]:
    """Extract only Contract D coverage fields and strip any stray prose keys."""
    def _non_neg_int(val: Any) -> int:
        if isinstance(val, int) and not isinstance(val, bool) and val >= 0:
            return val
        return 0

    raw_warnings = coverage.get("warnings")
    warnings = (
        [_clean_text(w) for w in raw_warnings if _clean_text(w)]
        if isinstance(raw_warnings, list)
        else []
    )
    status = _clean_text(coverage.get("completeness_status")).lower()
    if status not in ("complete", "partial", "degraded"):
        status = "degraded"

    sanitized: dict[str, Any] = {
        "chapters_total": _non_neg_int(coverage.get("chapters_total")),
        "chapters_done": _non_neg_int(coverage.get("chapters_done")),
        "chapters_incomplete": _non_neg_int(coverage.get("chapters_incomplete")),
        "chapters_failed": _non_neg_int(coverage.get("chapters_failed")),
        "missing_sections": _scrub_section_entries(coverage.get("missing_sections")),
        "truncated_sections": _scrub_section_entries(coverage.get("truncated_sections")),
        "completeness_status": status,
        "warnings": warnings,
    }
    # Ensure exact Contract D keyset.
    return {key: sanitized[key] for key in COVERAGE_REPORT_KEYS}


def _assert_no_prose_keys(node: Any) -> None:
    """Defense-in-depth check verifying zero forbidden prose keys exist anywhere."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.strip().casefold() in FORBIDDEN_PROSE_KEYS:
                raise ValueError(f"Forbidden prose key leaked into provenance: {key!r}")
            _assert_no_prose_keys(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_prose_keys(item)


def build_remote_provenance(
    candidate: dict[str, Any],
    session: dict[str, Any],
    policy: dict[str, Any],
    coverage: dict[str, Any] | None = None,
    *,
    requested_visibility: str | None = None,
) -> dict[str, Any]:
    """Build prose-free remote provenance metadata from candidate, session, policy, and coverage."""
    if not isinstance(candidate, dict):
        raise ValueError(f"candidate must be a dict, got {type(candidate).__name__}")
    if not isinstance(session, dict):
        raise ValueError(f"session must be a dict, got {type(session).__name__}")
    if not isinstance(policy, dict):
        raise ValueError(f"policy must be a dict, got {type(policy).__name__}")
    if coverage is not None and not isinstance(coverage, dict):
        raise ValueError(f"coverage must be a dict or None, got {type(coverage).__name__}")

    work = session.get("work") if isinstance(session.get("work"), dict) else {}

    provider = (
        _clean_text(candidate.get("provider"))
        or _clean_text(session.get("provider"))
        or "unknown"
    )
    source_name = _clean_text(candidate.get("source_name")) or provider
    item_id = _clean_text(candidate.get("item_id")) or _clean_text(work.get("item_id"))
    title = _clean_text(candidate.get("title")) or _clean_text(work.get("title"))

    authors = _normalize_authors(candidate.get("authors"))
    if not authors:
        authors = _normalize_authors(work.get("authors"))

    edition = _clean_optional_text(candidate.get("edition")) or _clean_optional_text(work.get("edition"))
    year = _normalize_year(candidate.get("year"))
    if year is None:
        year = _normalize_year(work.get("year"))

    fmt = _clean_optional_text(candidate.get("format")) or _clean_optional_text(work.get("format"))
    language = _clean_optional_text(candidate.get("language")) or _clean_optional_text(work.get("language"))
    identifiers = _normalize_identifiers(candidate.get("identifiers"), work.get("identifiers"))
    dedup_key = _clean_optional_text(candidate.get("dedup_key"))
    access_info = _clean_optional_text(candidate.get("access_info"))
    license_info = _clean_optional_text(candidate.get("license_info"))

    session_id = _clean_optional_text(session.get("session_id"))
    outline_mode = _clean_text(session.get("outline_mode")).lower() or "outline"
    confirmed_by_user = session.get("confirmed_by_user") is True
    publish_visibility = resolve_publish_visibility(requested_visibility, policy)

    coverage_summary = (
        _sanitize_coverage_payload(coverage)
        if coverage is not None
        else build_coverage_report(session)
    )

    provenance: dict[str, Any] = {
        "schema_version": 1,
        "provider": provider,
        "source_name": source_name,
        "item_id": item_id,
        "title": title,
        "authors": authors,
        "edition": edition,
        "year": year,
        "format": fmt,
        "language": language,
        "identifiers": identifiers,
        "dedup_key": dedup_key,
        "access_info": access_info,
        "license_info": license_info,
        "session_id": session_id,
        "outline_mode": outline_mode,
        "confirmed_by_user": confirmed_by_user,
        "publish_visibility": publish_visibility,
        "storage_mode": STORAGE_MODE,
        "coverage": coverage_summary,
    }
    _assert_no_prose_keys(provenance)
    return provenance


def render_provenance_markdown(provenance: dict[str, Any]) -> str:
    """Render a compact Markdown provenance and coverage section for Scope & Limits / Step 10."""
    if not isinstance(provenance, dict):
        raise ValueError(f"provenance must be a dict, got {type(provenance).__name__}")

    title = _clean_text(provenance.get("title")) or "Unknown title"
    authors = _normalize_authors(provenance.get("authors"))
    authors_str = ", ".join(authors) if authors else "Unknown author"

    edition = _clean_optional_text(provenance.get("edition"))
    year = _normalize_year(provenance.get("year"))
    if edition and year is not None:
        edition_str = f"{edition} ({year})"
    elif edition:
        edition_str = edition
    elif year is not None:
        edition_str = f"Unspecified ({year})"
    else:
        edition_str = "Unspecified"

    fmt = _clean_optional_text(provenance.get("format")) or "unknown"
    language = _clean_optional_text(provenance.get("language")) or "unknown"

    identifiers = _normalize_identifiers(provenance.get("identifiers"), None)
    isbn_str = ", ".join(identifiers["isbn"]) if identifiers["isbn"] else "None"
    doi_str = identifiers["doi"] or "None"

    provider = _clean_text(provenance.get("provider")) or "unknown"
    source_name = _clean_text(provenance.get("source_name")) or provider
    item_id = _clean_optional_text(provenance.get("item_id"))
    provider_parts = [provider]
    if source_name != provider:
        provider_parts.append(f"source: `{source_name}`")
    if item_id:
        provider_parts.append(f"ID: `{item_id}`")
    provider_str = f"{provider_parts[0]} ({', '.join(provider_parts[1:])})" if len(provider_parts) > 1 else provider_parts[0]

    access_info = _clean_optional_text(provenance.get("access_info")) or "Unspecified"
    license_info = _clean_optional_text(provenance.get("license_info")) or "Unspecified"

    confirmed = provenance.get("confirmed_by_user") is True
    confirmed_str = "yes (`confirmed_by_user: true`)" if confirmed else "no (`confirmed_by_user: false`)"
    outline_mode = _clean_text(provenance.get("outline_mode")) or "outline"
    visibility = _clean_text(provenance.get("publish_visibility")) or "private"
    storage_mode = _clean_text(provenance.get("storage_mode")) or STORAGE_MODE

    lines = [
        "### Remote Source & Provenance",
        f"- **Work:** {title} — {authors_str}",
        f"- **Edition / Format:** {edition_str} | **Format:** `{fmt}` | **Language:** `{language}`",
        f"- **Identifiers:** ISBN: {isbn_str} | DOI: {doi_str}",
        f"- **Provider:** {provider_str}",
        f"- **Access & License:** {access_info} | **License:** {license_info}",
        f"- **User Confirmation:** {confirmed_str} | **Outline mode:** `{outline_mode}`",
        f"- **Publish Visibility:** `{visibility}` | **Storage mode:** `{storage_mode}` (no raw prose or `full_text.txt` stored)",
    ]

    coverage = provenance.get("coverage")
    if isinstance(coverage, dict):
        lines.append(format_coverage_summary(_sanitize_coverage_payload(coverage)))

    return "\n".join(lines)
