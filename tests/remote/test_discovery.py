"""Unit tests for offline MCP discovery normalization and edition grouping."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.remote.discovery import (  # noqa: E402
    compute_dedup_key,
    format_candidate_selection_table,
    group_duplicate_editions,
    normalize_search_results,
    normalize_work_details,
)

CONTRACT_A_KEYS = {
    "provider",
    "item_id",
    "title",
    "authors",
    "edition",
    "year",
    "format",
    "language",
    "identifiers",
    "source_name",
    "access_info",
    "license_info",
    "dedup_key",
}


def test_zero_network_imports_in_remote_discovery():
    remote_dir = Path(__file__).resolve().parents[2] / "book_to_skill" / "remote"
    forbidden = {"urllib", "requests", "httpx", "socket", "http", "aiohttp"}

    for py_file in (remote_dir / "__init__.py", remote_dir / "discovery.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    assert root_mod not in forbidden, f"Forbidden import {alias.name} in {py_file}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                assert root_mod not in forbidden, f"Forbidden import {node.module} in {py_file}"


def test_normalize_search_results_title_search_libgen_mcp():
    raw_results = [
        {
            "md5": "0123456789abcdef0123456789abcdef",
            "title": "Synthetic Systems Engineering",
            "author": "Ada Example; Charles Sample",
            "edition": "2nd ed.",
            "year": "2022",
            "extension": "EPUB",
            "language": "English",
            "isbns": ["978-0-12-345678-9", "012345678X"],
            "source": "Synthetic LibGen Mirror",
            "access_info": "MCP search metadata + read",
            "license": "CC-BY-4.0",
        }
    ]

    normalized = normalize_search_results(raw_results, provider="libgen-mcp")
    assert len(normalized) == 1
    item = normalized[0]
    assert set(item.keys()) == CONTRACT_A_KEYS
    assert item["provider"] == "libgen-mcp"
    assert item["item_id"] == "0123456789abcdef0123456789abcdef"
    assert item["title"] == "Synthetic Systems Engineering"
    assert item["authors"] == ["Ada Example", "Charles Sample"]
    assert item["edition"] == "2nd ed."
    assert item["year"] == 2022
    assert item["format"] == "epub"
    assert item["language"] == "English"
    assert item["identifiers"] == {
        "isbn": ["9780123456789", "012345678X"],
        "doi": None,
    }
    assert item["source_name"] == "Synthetic LibGen Mirror"
    assert item["access_info"] == "MCP search metadata + read"
    assert item["license_info"] == "CC-BY-4.0"
    assert item["dedup_key"]


def test_normalize_search_results_author_and_alias_variants():
    raw_results = {
        "results": [
            {
                "id": 101,
                "book_title": "Distributed Testing Patterns",
                "authors": [{"name": "Elena Vance"}, {"full_name": "Marcus Cole"}, {"name": "Elena Vance"}],
                "pub_year": 2021,
                "mime_type": "application/pdf",
                "lang": "en",
                "isbn_13": "ISBN 978-1-4028-9462-6",
                "isbn_10": "140289462X (pbk)",
            },
            {
                "item_id": "auth-2",
                "title": "Single Author Comma Format",
                "author": "Lovelace, Ada",
                "format": ".azw3",
            },
            {
                "item_id": "auth-3",
                "title": "Two Authors Comma Format",
                "author": "Ada Example, Charles Sample",
                "format": "pdf",
            },
        ]
    }

    normalized = normalize_search_results(raw_results, provider="custom-mcp")
    assert len(normalized) == 3

    first, second, third = normalized
    assert first["provider"] == "custom-mcp"
    assert first["item_id"] == "101"
    assert first["authors"] == ["Elena Vance", "Marcus Cole"]
    assert first["year"] == 2021
    assert first["format"] == "pdf"
    assert first["language"] == "en"
    assert first["identifiers"]["isbn"] == ["9781402894626", "140289462X"]

    assert second["authors"] == ["Lovelace, Ada"]
    assert second["format"] == "azw3"
    assert third["authors"] == ["Ada Example", "Charles Sample"]


def test_normalize_search_results_isbn_and_doi_searches():
    raw_results = [
        {
            "item_id": "isbn-hit",
            "title": "ISBN Only Hit",
            "isbn": "978-0-306-40615-7, 0306406152",
            "published_date": "2019-11-04",
            "extension": "mobi",
        },
        {
            "item_id": "doi-hit",
            "title": "Synthetic Monograph on Queues",
            "author": "J. Doe",
            "identifiers": {"doi": "https://doi.org/10.5555/synthetic.2023.42", "isbn": []},
            "year": "c. 2023",
            "format": "pdf",
        },
        {
            "item_id": "doi-only-hit",
            "doi": "doi:10.5555/NO-TITLE-MONOGRAPH",
            "access": True,
        },
    ]

    normalized = normalize_search_results(raw_results)
    assert normalized[0]["identifiers"] == {"isbn": ["9780306406157", "0306406152"], "doi": None}
    assert normalized[0]["year"] == 2019

    assert normalized[1]["identifiers"]["doi"] == "10.5555/synthetic.2023.42"
    assert normalized[1]["year"] == 2023

    assert normalized[2]["identifiers"]["doi"] == "10.5555/NO-TITLE-MONOGRAPH"
    assert normalized[2]["access_info"] == "open_access"
    assert normalized[2]["dedup_key"] == "doi:10.5555/no-title-monograph"


def test_normalize_work_details_unwraps_and_sanitizes_messy_fields():
    raw_details = {
        "details": {
            "md5": "deadbeef1234",
            "title": "Resilient\u200b   Architecture\u202e Guide",
            "authors": ["  Dr. Nora\u200b Reid  ", "N/A", ""],
            "edition": "N/A",
            "year": False,
            "extension": "",
            "language": "null",
            "isbn": ["not-an-isbn", "978 0 262 03384 8"],
            "doi": "n/a",
            "license_info": "  ",
        }
    }

    details = normalize_work_details(raw_details)
    assert set(details.keys()) == CONTRACT_A_KEYS
    assert details["item_id"] == "deadbeef1234"
    assert details["title"] == "Resilient Architecture Guide"
    assert details["authors"] == ["Dr. Nora Reid"]
    assert details["edition"] is None
    assert details["year"] is None
    assert details["format"] is None
    assert details["language"] is None
    assert details["identifiers"] == {"isbn": ["9780262033848"], "doi": None}
    assert details["license_info"] is None
    assert details["source_name"] == "libgen-mcp"
    assert "libgen-mcp" in details["access_info"]


def test_normalize_invalid_inputs_raise_type_error():
    with pytest.raises(TypeError):
        normalize_work_details(["not", "a", "dict"])  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        normalize_search_results({"unexpected": []})

    with pytest.raises(TypeError):
        normalize_search_results("not-a-list")  # type: ignore[arg-type]


def test_group_duplicate_editions_and_variant_selection():
    candidates = normalize_search_results(
        [
            {
                "item_id": "id-epub-1",
                "title": "Algoritmos: Teoria e Prática",
                "author": "Silva, Carlos",
                "edition": "1st",
                "year": 2018,
                "format": "epub",
                "isbn": "978-0-11-111111-1",
                "source": "Mirror A",
            },
            {
                "item_id": "id-other-book",
                "title": "Algoritmos: Teoria e Prática",
                "author": "Helena Souza",
                "edition": "1st",
                "year": 2020,
                "format": "pdf",
                "source": "Mirror A",
            },
            {
                "item_id": "id-pdf-2",
                "title": "Algoritmos - Teoria e Pratica",
                "author": "Carlos Silva",
                "edition": "2nd",
                "year": 2022,
                "format": "pdf",
                "language": "Portuguese",
                "isbn": "978-0-22-222222-2",
                "source": "Mirror B",
            },
        ]
    )

    grouped = group_duplicate_editions(candidates)
    assert len(grouped) == 2

    first_group, second_group = grouped
    assert first_group["title"] == "Algoritmos: Teoria e Prática"
    assert first_group["language"] == "Portuguese"
    assert first_group["identifiers"]["isbn"] == ["9780111111111", "9780222222222"]
    assert len(first_group["editions"]) == 2
    assert len(first_group["variants"]) == 2

    # Individual selectable variants keep their distinct edition/format/id metadata
    v1, v2 = first_group["editions"]
    assert v1["item_id"] == "id-epub-1"
    assert v1["format"] == "epub"
    assert v1["edition"] == "1st"
    assert v2["item_id"] == "id-pdf-2"
    assert v2["format"] == "pdf"
    assert v2["edition"] == "2nd"

    # Mutating editions does not alias variants
    first_group["editions"].pop()
    assert len(first_group["variants"]) == 2

    # Different author stays in a separate group
    assert second_group["item_id"] == "id-other-book"
    assert len(second_group["editions"]) == 1


def test_group_duplicate_editions_handles_missing_dedup_key_and_empty_input():
    assert group_duplicate_editions([]) == []

    manual_candidates = [
        {"item_id": "m1", "title": "Manual Entry", "authors": ["A. Writer"], "format": "epub"},
        {"item_id": "m2", "title": "Manual Entry", "authors": ["A. Writer"], "format": "pdf"},
    ]
    grouped = group_duplicate_editions(manual_candidates)
    assert len(grouped) == 1
    assert grouped[0]["dedup_key"] == compute_dedup_key(manual_candidates[0])
    assert [ed["item_id"] for ed in grouped[0]["variants"]] == ["m1", "m2"]


def test_format_candidate_selection_table_flat_and_grouped():
    assert format_candidate_selection_table([]) == "No matching works found."

    candidates = normalize_search_results(
        [
            {
                "item_id": "item-1",
                "title": "Compiler Design Notes",
                "author": "Taylor Smith",
                "edition": "3rd",
                "year": 2024,
                "format": "epub",
                "source": "OpenCatalog",
            },
            {
                "item_id": "item-2",
                "title": "Compiler Design Notes",
                "author": "Taylor Smith",
                "edition": "3rd",
                "year": 2024,
                "format": "pdf",
                "source": "MirrorTwo",
            },
            {
                "item_id": "item-3",
                "title": "Minimal Record",
            },
        ]
    )

    flat_table = format_candidate_selection_table(candidates)
    assert "1. Compiler Design Notes" in flat_table
    assert "Taylor Smith" in flat_table
    assert "3rd" in flat_table
    assert "2024" in flat_table
    assert "epub" in flat_table
    assert "libgen-mcp/OpenCatalog" in flat_table
    assert "3. Minimal Record — Unknown author" in flat_table
    assert "None" not in flat_table

    grouped_table = format_candidate_selection_table(group_duplicate_editions(candidates))
    assert "1. Compiler Design Notes — Taylor Smith (2 editions)" in grouped_table
    assert "1.1 Edition: 3rd | Year: 2024 | Format: epub | Source: libgen-mcp/OpenCatalog | ID: item-1" in grouped_table
    assert "1.2 Edition: 3rd | Year: 2024 | Format: pdf | Source: libgen-mcp/MirrorTwo | ID: item-2" in grouped_table
    assert "2. Minimal Record — Unknown author" in grouped_table


def test_normalize_search_results_includes_open_access_and_compacts_long_ids():
    payload = {
        "results": [
            {
                "md5": "caf74dbcc14e6d9eb647117af8596783",
                "title": "Site Reliability Engineering",
                "author": "Betsy Beyer",
                "year": 2016,
                "extension": "pdf",
            }
        ],
        "open_access": [
            {
                "doi": "10.1000/sre-open-example",
                "title": "Site Reliability Engineering Paper",
                "authors": ["Betsy Beyer"],
                "year": 2016,
                "origin": "openalex",
                "is_oa": True,
                "format": "pdf",
            }
        ],
    }

    normalized = normalize_search_results(payload)
    assert len(normalized) == 2
    # open_access items surface first with open-access annotation
    assert normalized[0]["access_info"] == "open-access"
    assert normalized[0]["source_name"] == "openalex"
    assert normalized[0]["identifiers"]["doi"] == "10.1000/sre-open-example"

    table = format_candidate_selection_table(normalized)
    assert "Access: open-access" in table
    assert "DOI: 10.1000/sre-open-example" in table
    # 32-char MD5 is compacted for display while full item_id stays intact in normalized dict
    assert "ID: caf74dbc…" in table
    assert "caf74dbcc14e6d9eb647117af8596783" not in table
    assert normalized[1]["item_id"] == "caf74dbcc14e6d9eb647117af8596783"

    oa_only = normalize_search_results({"open_access": payload["open_access"]})
    assert len(oa_only) == 1
    assert oa_only[0]["source_name"] == "openalex"


def test_unverified_crossref_in_open_access_bucket_is_not_flagged_open_access():
    payload = {
        "results": [
            {"md5": "caf74dbcc14e6d9eb647117af8596783", "title": "SRE Book", "author": "Betsy Beyer"},
        ],
        "open_access": [
            {
                "doi": "10.1007/979-8-8688-1448-8_1",
                "title": "Introduction to SRE (Paywalled Chapter)",
                "origin": "crossref",
            },
            {
                "doi": "10.48550/ARXIV.2505.01926",
                "title": "SRE Open arXiv Paper",
                "origin": "arxiv",
                "is_oa": True,
            },
        ],
    }

    normalized = normalize_search_results(payload)
    assert [item["title"] for item in normalized] == [
        "SRE Open arXiv Paper",
        "SRE Book",
        "Introduction to SRE (Paywalled Chapter)",
    ]
    assert normalized[0]["access_info"] == "open-access"
    assert "metadata-only" in normalized[2]["access_info"]
    assert "open-access" not in normalized[2]["access_info"]
