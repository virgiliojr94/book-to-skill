"""Deterministic, offline normalization and grouping for MCP search/detail payloads."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from book_to_skill.sanitize import sanitize_extracted_text

_NULLISH_MARKERS = frozenset({"", "null", "none", "n/a", "na", "unknown"})
_AUTHOR_SUFFIXES = frozenset({"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "phd", "ph.d.", "md", "m.d."})
_MIME_TO_FORMAT = {
    "application/pdf": "pdf",
    "application/epub+zip": "epub",
    "application/x-mobipocket-ebook": "mobi",
    "application/vnd.amazon.ebook": "azw",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/rtf": "rtf",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/html": "html",
    "application/xhtml+xml": "xhtml",
}
_WRAPPER_RESULT_LIST_KEYS = ("results", "items", "hits", "records", "books", "works")
_WRAPPER_DETAIL_KEYS = ("details", "work", "book", "item", "result", "record")

_YEAR_MODERN_RE = re.compile(r"(?<!\d)([12]\d{3})(?!\d)")
_YEAR_ANY_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|urn:doi:|doi:)\s*", re.IGNORECASE)
_ISBN_PREFIX_RE = re.compile(r"^(?:urn:isbn:|isbn(?:-?(?:10|13))?[:\s]*)", re.IGNORECASE)
_ISBN_VALID_RE = re.compile(r"^(?:\d{9}[\dX]|\d{13})$")


def _clean_text(value: Any) -> str:
    """Convert a scalar value to sanitized, single-spaced text."""
    if value is None or isinstance(value, bool):
        return ""
    text = str(value)
    sanitized, _ = sanitize_extracted_text(text)
    return re.sub(r"\s+", " ", sanitized).strip()


def _clean_optional_text(value: Any, *, treat_unknown_as_none: bool = False) -> str | None:
    """Normalize optional text fields, returning None when absent or empty."""
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    if treat_unknown_as_none and cleaned.lower() in _NULLISH_MARKERS:
        return None
    if cleaned.lower() in {"null", "none"}:
        return None
    return cleaned


def _pick_first(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-empty value for any key in ``keys``."""
    for key in keys:
        if key not in raw:
            continue
        val = raw[key]
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        if isinstance(val, (list, tuple, dict, set)) and len(val) == 0:
            continue
        return val
    return None


def _split_author_string(author_text: str) -> list[str]:
    """Split an author string into individual names without breaking 'Last, First'."""
    cleaned = _clean_text(author_text)
    if not cleaned:
        return []

    if any(sep in cleaned for sep in (";", "|", "\n")):
        parts = re.split(r"[;|\n]+", cleaned)
        return [part.strip() for part in parts if part.strip()]

    if "," in cleaned:
        comma_parts = [part.strip() for part in cleaned.split(",") if part.strip()]
        if len(comma_parts) > 2:
            # Re-attach trailing generational/academic suffixes like "Smith, Jr."
            merged: list[str] = []
            for part in comma_parts:
                if merged and part.lower() in _AUTHOR_SUFFIXES:
                    merged[-1] = f"{merged[-1]}, {part}"
                else:
                    merged.append(part)
            return merged
        if len(comma_parts) == 2:
            left, right = comma_parts
            if right.lower() in _AUTHOR_SUFFIXES:
                return [cleaned]
            if len(left.split()) >= 2 and len(right.split()) >= 2:
                return [left, right]
        return [cleaned]

    return [cleaned]


def _normalize_authors(raw: dict[str, Any]) -> list[str]:
    """Extract and deduplicate author names from varied MCP payload keys."""
    val = _pick_first(
        raw,
        ("authors", "author", "creators", "creator", "writers", "writer", "contributors"),
    )
    if val is None:
        return []

    raw_items: Iterable[Any]
    if isinstance(val, str):
        raw_items = [val]
    elif isinstance(val, dict):
        raw_items = [val]
    elif isinstance(val, (list, tuple)):
        raw_items = val
    else:
        raw_items = [val]

    authors: list[str] = []
    seen: set[str] = set()
    for entry in raw_items:
        if isinstance(entry, dict):
            name = _pick_first(entry, ("name", "full_name", "author", "display_name", "value"))
            candidates = _split_author_string(name) if isinstance(name, str) else ([_clean_text(name)] if name else [])
        elif isinstance(entry, str):
            candidates = _split_author_string(entry)
        else:
            cleaned = _clean_text(entry)
            candidates = [cleaned] if cleaned else []

        for author in candidates:
            norm = _clean_text(author)
            if not norm or norm.lower() in _NULLISH_MARKERS:
                continue
            key = norm.casefold()
            if key not in seen:
                seen.add(key)
                authors.append(norm)
    return authors


def _normalize_year(raw: dict[str, Any]) -> int | None:
    """Extract a 4-digit publication year (or valid integer year) as int | None."""
    val = _pick_first(
        raw,
        (
            "year",
            "pub_year",
            "publication_year",
            "publish_year",
            "published_year",
            "date",
            "pub_date",
            "published_date",
        ),
    )
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val if 1 <= val <= 2999 else None
    if isinstance(val, float) and val.is_integer():
        year_int = int(val)
        return year_int if 1 <= year_int <= 2999 else None

    text = _clean_text(val)
    if not text:
        return None
    match = _YEAR_MODERN_RE.search(text) or _YEAR_ANY_RE.search(text)
    if not match:
        return None
    year_int = int(match.group(1))
    return year_int if 1000 <= year_int <= 2999 else None


def _normalize_format(raw: dict[str, Any]) -> str | None:
    """Normalize file extension / format / MIME type to lowercase extension."""
    val = _pick_first(
        raw,
        ("format", "extension", "ext", "file_format", "filetype", "mime_type", "mimetype"),
    )
    cleaned = _clean_optional_text(val, treat_unknown_as_none=True)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered in _MIME_TO_FORMAT:
        return _MIME_TO_FORMAT[lowered]
    lowered = lowered.lstrip(".")
    return lowered or None


def _clean_isbn_token(token: str) -> str | None:
    """Normalize a single ISBN token; return None if it is not a 10/13-char ISBN."""
    cleaned = _clean_text(token)
    if not cleaned:
        return None
    cleaned = _ISBN_PREFIX_RE.sub("", cleaned)
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned).strip()
    compact = re.sub(r"[\s-]+", "", cleaned).upper()
    if _ISBN_VALID_RE.match(compact):
        return compact
    return None


def _clean_doi_value(value: Any) -> str | None:
    """Normalize a DOI string by stripping URL/scheme prefixes."""
    if isinstance(value, (list, tuple)):
        for item in value:
            doi = _clean_doi_value(item)
            if doi:
                return doi
        return None
    cleaned = _clean_optional_text(value, treat_unknown_as_none=True)
    if not cleaned:
        return None
    stripped = _DOI_PREFIX_RE.sub("", cleaned).strip()
    if not stripped or stripped.lower() in _NULLISH_MARKERS:
        return None
    return stripped


def _collect_isbn_values(value: Any, out: list[str], seen: set[str]) -> None:
    """Append normalized ISBN strings from a scalar or sequence into ``out``."""
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _collect_isbn_values(item, out, seen)
        return
    text = _clean_text(value)
    if not text:
        return
    for part in re.split(r"[,;|\n]+", text):
        part = part.strip()
        if not part:
            continue
        direct = _clean_isbn_token(part)
        if direct:
            if direct not in seen:
                seen.add(direct)
                out.append(direct)
            continue
        # Fallback for space-separated ISBNs in a single field
        for subpart in part.split():
            isbn = _clean_isbn_token(subpart)
            if isbn and isbn not in seen:
                seen.add(isbn)
                out.append(isbn)


def _normalize_identifiers(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize ISBN list and DOI from nested or top-level MCP fields."""
    isbns: list[str] = []
    seen_isbns: set[str] = set()
    doi: str | None = None

    nested = raw.get("identifiers")
    if isinstance(nested, dict):
        for key in ("isbn", "isbns", "isbn13", "isbn_13", "isbn10", "isbn_10"):
            _collect_isbn_values(nested.get(key), isbns, seen_isbns)
        doi = _clean_doi_value(nested.get("doi"))
    elif isinstance(nested, (list, tuple)):
        for entry in nested:
            if isinstance(entry, str) and entry.lower().startswith(("10.", "doi:", "https://doi.org/", "http://doi.org/", "urn:doi:")):
                doi = doi or _clean_doi_value(entry)
            else:
                _collect_isbn_values(entry, isbns, seen_isbns)

    for key in ("isbn", "isbns", "isbn13", "isbn_13", "isbn10", "isbn_10"):
        _collect_isbn_values(raw.get(key), isbns, seen_isbns)

    if doi is None:
        doi = _clean_doi_value(_pick_first(raw, ("doi", "dois")))

    generic_id = raw.get("identifier")
    if isinstance(generic_id, str):
        lowered = generic_id.strip().lower()
        if lowered.startswith(("10.", "doi:", "https://doi.org/", "http://doi.org/", "urn:doi:")):
            doi = doi or _clean_doi_value(generic_id)
        else:
            _collect_isbn_values(generic_id, isbns, seen_isbns)

    return {"isbn": isbns, "doi": doi}


def _normalize_key_text(text: str) -> str:
    """Fold Unicode accents, strip punctuation, and collapse whitespace for dedup keys."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    chars: list[str] = []
    for ch in decomposed:
        cat = unicodedata.category(ch)
        if cat == "Mn":
            continue
        if cat[0] in ("P", "S", "Z", "C"):
            chars.append(" ")
        else:
            chars.append(ch.casefold())
    return " ".join("".join(chars).split())


def _normalize_primary_author_for_key(author: str) -> str:
    """Canonicalize 'Last, First' and 'First Last' into a comparable key string."""
    cleaned = _clean_text(author)
    if not cleaned:
        return ""
    if "," in cleaned:
        left, right = [part.strip() for part in cleaned.split(",", 1)]
        if left and right and right.lower() not in _AUTHOR_SUFFIXES:
            cleaned = f"{right} {left}"
    return _normalize_key_text(cleaned)


def compute_dedup_key(candidate: dict[str, Any]) -> str:
    """Compute a deterministic work-level dedup_key from title+author, DOI, or ISBN."""
    title = _clean_text(candidate.get("title"))
    norm_title = _normalize_key_text(title)

    authors = candidate.get("authors")
    primary_author = ""
    if isinstance(authors, (list, tuple)) and authors:
        primary_author = _normalize_primary_author_for_key(str(authors[0]))
    elif isinstance(authors, str):
        primary_author = _normalize_primary_author_for_key(authors)

    identifiers = candidate.get("identifiers")
    doi = None
    isbns: list[str] = []
    if isinstance(identifiers, dict):
        doi = _clean_doi_value(identifiers.get("doi"))
        raw_isbns = identifiers.get("isbn")
        if isinstance(raw_isbns, (list, tuple)):
            isbns = [str(x).strip() for x in raw_isbns if str(x).strip()]

    if norm_title and primary_author:
        return f"work:{norm_title}|{primary_author}"
    if doi:
        return f"doi:{doi.casefold()}"
    if isbns:
        return f"isbn:{isbns[0]}"
    if norm_title:
        return f"title:{norm_title}"

    provider = _clean_text(candidate.get("provider")) or "unknown"
    item_id = _clean_text(candidate.get("item_id"))
    if item_id:
        return f"item:{provider.casefold()}:{item_id}"
    return f"item:{provider.casefold()}:unknown"


def _resolve_provider(raw: dict[str, Any], provider: str) -> str:
    """Resolve provider name, honoring explicit non-default argument or payload field."""
    arg_provider = _clean_text(provider)
    raw_provider = _clean_text(raw.get("provider"))
    if arg_provider and arg_provider != "libgen-mcp":
        return arg_provider
    return raw_provider or arg_provider or "libgen-mcp"


def _unwrap_details_dict(raw_details: dict[str, Any]) -> dict[str, Any]:
    """Unwrap common single-item MCP response envelopes when top-level lacks work keys."""
    core_keys = {"title", "book_title", "item_id", "id", "md5", "isbn", "doi"}
    if any(key in raw_details for key in core_keys):
        return raw_details
    for wrapper_key in _WRAPPER_DETAIL_KEYS:
        inner = raw_details.get(wrapper_key)
        if isinstance(inner, dict):
            return inner
    return raw_details


def normalize_work_details(raw_details: dict[str, Any], provider: str = "libgen-mcp") -> dict[str, Any]:
    """Normalize a single MCP search item or get_details payload into Contract A."""
    if not isinstance(raw_details, dict):
        raise TypeError("raw_details must be a dict")

    raw = _unwrap_details_dict(raw_details)
    resolved_provider = _resolve_provider(raw, provider)

    item_id_val = _pick_first(
        raw,
        ("item_id", "id", "md5", "book_id", "work_id", "doc_id", "olid", "key", "sha256", "sha1"),
    )
    item_id = _clean_text(item_id_val)

    title_val = _pick_first(raw, ("title", "book_title", "work_title", "name"))
    title = _clean_text(title_val)

    authors = _normalize_authors(raw)
    edition = _clean_optional_text(
        _pick_first(raw, ("edition", "ed", "edition_info", "version")),
        treat_unknown_as_none=True,
    )
    year = _normalize_year(raw)
    fmt = _normalize_format(raw)
    language_raw = _pick_first(raw, ("language", "lang", "languages"))
    if isinstance(language_raw, (list, tuple)):
        language_raw = next((item for item in language_raw if _clean_text(item)), None)
    language = _clean_optional_text(language_raw, treat_unknown_as_none=True)

    identifiers = _normalize_identifiers(raw)

    source_name = (
        _clean_text(_pick_first(raw, ("source_name", "source", "repository", "mirror", "catalog", "collection")))
        or resolved_provider
    )

    access_val = _pick_first(
        raw,
        ("access_info", "access", "availability", "access_status", "access_url"),
    )
    if isinstance(access_val, bool):
        access_info = "open_access" if access_val else "restricted_access"
    else:
        access_info = _clean_text(access_val) or f"MCP remote read via {resolved_provider}"

    license_info = _clean_optional_text(
        _pick_first(raw, ("license_info", "license", "rights", "copyright", "license_url")),
        treat_unknown_as_none=True,
    )

    normalized: dict[str, Any] = {
        "provider": resolved_provider,
        "item_id": item_id,
        "title": title,
        "authors": authors,
        "edition": edition,
        "year": year,
        "format": fmt,
        "language": language,
        "identifiers": identifiers,
        "source_name": source_name,
        "access_info": access_info,
        "license_info": license_info,
    }
    normalized["dedup_key"] = compute_dedup_key(normalized)
    return normalized


def normalize_search_results(
    raw_results: list[dict[str, Any]] | dict[str, Any],
    provider: str = "libgen-mcp",
) -> list[dict[str, Any]]:
    """Normalize a list (or wrapped dict) of MCP search payloads into Contract A dicts."""
    if raw_results is None:
        return []
    if isinstance(raw_results, dict):
        extracted = None
        for key in _WRAPPER_RESULT_LIST_KEYS:
            if isinstance(raw_results.get(key), list):
                extracted = raw_results[key]
                break
        if extracted is None:
            raise TypeError("raw_results dict must contain a list under results/items/hits/records")
        items = extracted
    elif isinstance(raw_results, (list, tuple)):
        items = list(raw_results)
    else:
        raise TypeError("raw_results must be a list of dicts")

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(normalize_work_details(item, provider=provider))
    return normalized


def _clone_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of a Contract A dict with copied mutable collections."""
    cloned = dict(candidate)
    authors = cloned.get("authors")
    if isinstance(authors, list):
        cloned["authors"] = list(authors)
    identifiers = cloned.get("identifiers")
    if isinstance(identifiers, dict):
        cloned["identifiers"] = {
            "isbn": list(identifiers.get("isbn") or []),
            "doi": identifiers.get("doi"),
        }
    return cloned


def group_duplicate_editions(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically group candidates sharing dedup_key while keeping selectable editions."""
    if not candidates:
        return []

    groups_by_key: dict[str, list[dict[str, Any]]] = {}
    ordered_keys: list[str] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        item = _clone_candidate(candidate)
        key = _clean_text(item.get("dedup_key")) or compute_dedup_key(item)
        item["dedup_key"] = key
        if key not in groups_by_key:
            groups_by_key[key] = []
            ordered_keys.append(key)
        groups_by_key[key].append(item)

    grouped: list[dict[str, Any]] = []
    for key in ordered_keys:
        editions = groups_by_key[key]
        rep = _clone_candidate(editions[0])

        merged_isbns: list[str] = []
        seen_isbns: set[str] = set()
        merged_doi = rep.get("identifiers", {}).get("doi") if isinstance(rep.get("identifiers"), dict) else None

        for edition in editions:
            idents = edition.get("identifiers")
            if isinstance(idents, dict):
                for isbn in idents.get("isbn") or []:
                    if isbn not in seen_isbns:
                        seen_isbns.add(isbn)
                        merged_isbns.append(isbn)
                if merged_doi is None and idents.get("doi"):
                    merged_doi = idents.get("doi")

            for field in ("edition", "year", "language", "license_info"):
                if rep.get(field) is None and edition.get(field) is not None:
                    rep[field] = edition.get(field)
            if not rep.get("authors") and edition.get("authors"):
                rep["authors"] = list(edition["authors"])

        rep["identifiers"] = {"isbn": merged_isbns, "doi": merged_doi}
        rep["dedup_key"] = key
        rep["editions"] = [_clone_candidate(ed) for ed in editions]
        rep["variants"] = [_clone_candidate(ed) for ed in editions]
        grouped.append(rep)

    return grouped


def _format_source_label(candidate: dict[str, Any]) -> str:
    """Format provider/source display without duplicating identical names."""
    provider = _clean_text(candidate.get("provider")) or "unknown"
    source_name = _clean_text(candidate.get("source_name"))
    if source_name and source_name != provider:
        return f"{provider}/{source_name}"
    return provider


def _format_edition_line(candidate: dict[str, Any]) -> str:
    """Format edition/year/format/source/id summary for one selectable item."""
    edition = _clean_text(candidate.get("edition")) or "-"
    year_val = candidate.get("year")
    year = str(year_val) if year_val is not None else "-"
    fmt = _clean_text(candidate.get("format")) or "-"
    source = _format_source_label(candidate)
    item_id = _clean_text(candidate.get("item_id")) or "-"
    return f"Edition: {edition} | Year: {year} | Format: {fmt} | Source: {source} | ID: {item_id}"


def format_candidate_selection_table(candidates: list[dict[str, Any]]) -> str:
    """Render a human-readable numbered selection summary for flat or grouped candidates."""
    if not candidates:
        return "No matching works found."

    lines: list[str] = []
    for idx, candidate in enumerate(candidates, start=1):
        title = _clean_text(candidate.get("title")) or "(Untitled)"
        authors_val = candidate.get("authors")
        if isinstance(authors_val, (list, tuple)):
            authors_list = [_clean_text(a) for a in authors_val if _clean_text(a)]
        elif isinstance(authors_val, str):
            authors_list = [_clean_text(authors_val)] if _clean_text(authors_val) else []
        else:
            authors_list = []
        authors_str = ", ".join(authors_list) if authors_list else "Unknown author"

        editions = candidate.get("editions")
        if not isinstance(editions, list):
            editions = candidate.get("variants") if isinstance(candidate.get("variants"), list) else None

        if editions and len(editions) > 1:
            lines.append(f"{idx}. {title} — {authors_str} ({len(editions)} editions)")
            for sub_idx, edition_item in enumerate(editions, start=1):
                lines.append(f"   {idx}.{sub_idx} {_format_edition_line(edition_item)}")
        else:
            item = editions[0] if editions and len(editions) == 1 else candidate
            lines.append(f"{idx}. {title} — {authors_str} | {_format_edition_line(item)}")

    return "\n".join(lines)
