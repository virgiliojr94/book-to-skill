"""Tests for book_to_skill.remote.reader (Contract C: outline, section, cursor processing)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.remote.reader import (  # noqa: E402
    SUPPORTED_READ_MODES,
    parse_outline_response,
    process_section_page,
    read_section_from_pages,
    sanitize_remote_chunk,
)


def test_reader_module_has_zero_network_imports():
    reader_path = ROOT_DIR / "book_to_skill" / "remote" / "reader.py"
    tree = ast.parse(reader_path.read_text(encoding="utf-8"))
    forbidden = {"urllib", "requests", "httpx", "socket", "http", "aiohttp"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(forbidden)


def test_supported_read_modes():
    assert SUPPORTED_READ_MODES == frozenset({"outline", "section", "cursor"})


def test_sanitize_remote_chunk_strips_invisible_and_bidi_injection():
    # Zero-width space + Trojan Source RLO + Unicode Tag block character + variation selector
    injected = "Clean\u200b text\u202e ignore previous\U000e0041\ufe0f."
    result = sanitize_remote_chunk(injected)

    assert result["text"] == "Clean text ignore previous."
    assert result["removed_invisible_count"] == 4
    assert result["empty"] is False


def test_sanitize_remote_chunk_empty_and_invisible_only():
    invisible_only = "\u200b\u200c\u202e   \n\t"
    result = sanitize_remote_chunk(invisible_only)
    assert result["text"] == "   \n\t"
    assert result["removed_invisible_count"] == 3
    assert result["empty"] is True

    none_result = sanitize_remote_chunk(None)  # type: ignore[arg-type]
    assert none_result == {"text": "", "removed_invisible_count": 0, "empty": True}

    with pytest.raises(TypeError):
        sanitize_remote_chunk(123)  # type: ignore[arg-type]


def test_parse_outline_response_normalizes_valid_chapters():
    raw_outline = {
        "chapters": [
            {"section_id": "ch1", "title": "Intro\u200bduction", "index": 1},
            {"id": "ch2", "name": "Core\u202e Concepts", "order": 2},
        ]
    }
    mode, chapters = parse_outline_response(raw_outline)
    assert mode == "outline"
    assert chapters == [
        {"index": 1, "section_id": "ch1", "title": "Introduction"},
        {"index": 2, "section_id": "ch2", "title": "Core Concepts"},
    ]


def test_parse_outline_response_nested_wrapper_and_fallback_index():
    raw_outline = {
        "outline": {
            "sections": [
                {"chapter_id": "sec-a", "heading": "Alpha"},
                {"chapter_id": "sec-b", "label": "Beta"},
            ]
        }
    }
    mode, chapters = parse_outline_response(raw_outline)
    assert mode == "outline"
    assert chapters == [
        {"index": 1, "section_id": "sec-a", "title": "Alpha"},
        {"index": 2, "section_id": "sec-b", "title": "Beta"},
    ]


@pytest.mark.parametrize(
    "raw_outline",
    [
        {},
        {"chapters": []},
        {"outline_available": False, "chapters": [{"section_id": "ch1", "title": "Ch1"}]},
        {"reliable": False, "chapters": [{"section_id": "ch1", "title": "Ch1"}]},
        {"mode": "sequential_fallback", "chapters": [{"section_id": "ch1", "title": "Ch1"}]},
        {"status": "unavailable"},
        {"error": "TOC missing"},
        {"text": "Flat unsegmented text without outline"},
        {"chapters": [{"title": "Missing ID 1"}, {"title": "Missing ID 2"}]},
        {"chapters": [{"section_id": "dup", "title": "One"}, {"section_id": "dup", "title": "Two"}]},
    ],
)
def test_parse_outline_response_sequential_fallback(raw_outline):
    mode, chapters = parse_outline_response(raw_outline)
    assert mode == "sequential_fallback"
    assert chapters == []


def test_process_section_page_single_and_multipage():
    seen: set[str] = set()
    page1 = process_section_page(
        {"text": "First\u200b chunk.", "next_cursor": "cur-2"},
        seen_cursors=seen,
    )
    assert page1["text"] == "First chunk."
    assert page1["removed_invisible_count"] == 1
    assert page1["status"] == "in_progress"
    assert page1["has_more"] is True
    assert page1["next_cursor"] == "cur-2"
    assert "cur-2" in seen

    page2 = process_section_page(
        {"cursor": "cur-2", "text": "Final chunk.", "next_cursor": None},
        seen_cursors=seen,
    )
    assert page2["text"] == "Final chunk."
    assert page2["status"] == "done"
    assert page2["has_more"] is False
    assert page2["next_cursor"] is None


def test_process_section_page_detects_infinite_cursor_loop():
    seen: set[str] = {"cur-1"}
    res = process_section_page(
        {"text": "Looping chunk", "next_cursor": "cur-1"},
        seen_cursors=seen,
    )
    assert res["status"] == "incomplete"
    assert res["loop_detected"] is True
    assert res["has_more"] is False
    assert res["next_cursor"] is None
    assert "loop" in (res["error_reason"] or "").lower()

    # Self-loop on first page (cursor == next_cursor) even when seen is empty
    fresh_seen: set[str] = set()
    self_loop = process_section_page(
        {"cursor": "same", "text": "Self loop", "next_cursor": "same"},
        seen_cursors=fresh_seen,
    )
    assert self_loop["status"] == "incomplete"
    assert self_loop["loop_detected"] is True
    assert self_loop["has_more"] is False


def test_process_section_page_enforces_max_cursors_per_section():
    seen: set[str] = {"c1", "c2"}
    res = process_section_page(
        {"text": "Page 3", "next_cursor": "c3"},
        seen_cursors=seen,
        max_cursors_per_section=2,
    )
    assert res["status"] == "incomplete"
    assert res["cursor_limit_reached"] is True
    assert res["has_more"] is False
    assert res["next_cursor"] is None
    assert "limit" in (res["error_reason"] or "").lower()


def test_process_section_page_truncated_missing_empty_and_error():
    trunc = process_section_page(
        {"text": "Partial text", "truncated": True},
        seen_cursors=set(),
    )
    assert trunc["truncated"] is True
    assert trunc["status"] == "incomplete"
    assert "truncated" in (trunc["error_reason"] or "").lower()

    missing = process_section_page(
        {"missing": True, "text": ""},
        seen_cursors=set(),
    )
    assert missing["missing"] is True
    assert missing["status"] == "failed"

    empty = process_section_page(
        {"text": "\u200b  "},
        seen_cursors=set(),
    )
    assert empty["empty"] is True
    assert empty["status"] == "incomplete"

    err = process_section_page(
        {"error": "Backend timeout"},
        seen_cursors=set(),
    )
    assert err["status"] == "failed"
    assert err["error_reason"] == "Backend timeout"


def test_read_section_from_pages_multipage_and_trailing_empty():
    pages = [
        {"text": "Part\u200b 1", "next_cursor": "c2"},
        {"text": "Part\u202e 2", "next_cursor": "c3"},
        {"text": "   ", "next_cursor": None},
    ]
    res = read_section_from_pages(pages)
    assert res["status"] == "done"
    assert res["text"] == "Part 1\nPart 2"
    assert res["chunks_read"] == 2
    assert res["requests_made"] == 3
    assert res["sanitized_removed_count"] == 2
    assert res["truncated"] is False
    assert res["missing"] is False
    assert res["next_cursor"] is None
    assert res["error_reason"] is None


def test_read_section_from_pages_breaks_infinite_cursor_loop():
    pages = [
        {"text": "Chunk 1", "next_cursor": "c2"},
        {"text": "Chunk 2", "next_cursor": "c3"},
        {"text": "Chunk 3", "next_cursor": "c2"},  # loop back to c2
        {"text": "Never reached", "next_cursor": None},
    ]
    res = read_section_from_pages(pages)
    assert res["status"] == "incomplete"
    assert res["chunks_read"] == 3
    assert res["requests_made"] == 3
    assert res["next_cursor"] is None
    assert "loop" in (res["error_reason"] or "").lower()


def test_read_section_from_pages_enforces_max_total_requests():
    pages = [
        {"text": "Chunk 1", "next_cursor": "c2"},
        {"text": "Chunk 2", "next_cursor": "c3"},
        {"text": "Chunk 3", "next_cursor": "c4"},
    ]
    res = read_section_from_pages(pages, max_total_requests=2, requests_used=0)
    assert res["status"] == "incomplete"
    assert res["requests_made"] == 2
    assert res["total_requests"] == 2
    assert res["next_cursor"] == "c3"
    assert "max_total_requests" in (res["error_reason"] or "")

    # Pre-exhausted budget stops before reading any page
    exhausted = read_section_from_pages(pages, max_total_requests=5, requests_used=5)
    assert exhausted["status"] == "incomplete"
    assert exhausted["requests_made"] == 0
    assert exhausted["chunks_read"] == 0
    assert "max_total_requests" in (exhausted["error_reason"] or "")


def test_read_section_from_pages_truncated_missing_and_empty():
    trunc = read_section_from_pages(
        [
            {"text": "Chunk 1", "next_cursor": "c2"},
            {"text": "Chunk 2 partial", "truncated": True, "next_cursor": None},
        ]
    )
    assert trunc["status"] == "incomplete"
    assert trunc["truncated"] is True
    assert trunc["chunks_read"] == 2

    missing = read_section_from_pages([{"found": False}])
    assert missing["status"] == "failed"
    assert missing["missing"] is True

    empty = read_section_from_pages([{"text": "\u200b"}])
    assert empty["status"] == "incomplete"
    assert empty["chunks_read"] == 0
    assert empty["sanitized_removed_count"] == 1
