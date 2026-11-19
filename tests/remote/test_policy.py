"""Tests for book_to_skill.remote.policy (Contract B: provider policy & copyright gate)."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.remote.policy import (  # noqa: E402
    DEFAULT_POLICY,
    POLICY_ENV_VAR,
    build_access_copyright_notice,
    check_provider_allowed,
    load_policy,
    resolve_publish_visibility,
    verify_user_confirmation,
)


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
        "dedup_key": "systems-architecture-primer|lovelace",
    }


def test_default_policy_matches_contract_b():
    assert DEFAULT_POLICY == {
        "enabled_providers": ["*"],
        "blocked_providers": [],
        "require_explicit_confirmation": True,
        "default_publish_visibility": "private",
        "allow_public_publish": False,
        "warn_mcp_temporary_cache": True,
    }


def test_policy_module_has_zero_network_imports():
    policy_path = ROOT_DIR / "book_to_skill" / "remote" / "policy.py"
    tree = ast.parse(policy_path.read_text(encoding="utf-8"))
    forbidden = {"urllib", "requests", "httpx", "socket", "http", "aiohttp"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(forbidden)


def test_load_policy_returns_isolated_copy(monkeypatch):
    monkeypatch.delenv(POLICY_ENV_VAR, raising=False)
    policy = load_policy()
    assert policy == DEFAULT_POLICY

    policy["enabled_providers"].append("custom")
    policy["blocked_providers"].append("bad")
    assert DEFAULT_POLICY["enabled_providers"] == ["*"]
    assert DEFAULT_POLICY["blocked_providers"] == []


def test_load_policy_from_env_inline_json(monkeypatch):
    monkeypatch.setenv(
        POLICY_ENV_VAR,
        json.dumps(
            {
                "enabled_providers": ["libgen-mcp", "openlibrary-mcp"],
                "blocked_providers": ["untrusted-mcp"],
                "allow_public_publish": False,
                "warn_mcp_temporary_cache": False,
            }
        ),
    )
    policy = load_policy()
    assert policy["enabled_providers"] == ["libgen-mcp", "openlibrary-mcp"]
    assert policy["blocked_providers"] == ["untrusted-mcp"]
    assert policy["warn_mcp_temporary_cache"] is False
    assert policy["require_explicit_confirmation"] is True


def test_load_policy_from_env_json_file_path(monkeypatch, tmp_path):
    policy_file = tmp_path / "remote-policy.json"
    policy_file.write_text(
        json.dumps(
            {
                "enabled_providers": ["archive-mcp"],
                "blocked_providers": ["libgen-mcp"],
                "require_explicit_confirmation": True,
                "default_publish_visibility": "private",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(POLICY_ENV_VAR, str(policy_file))
    policy = load_policy()
    assert policy["enabled_providers"] == ["archive-mcp"]
    assert policy["blocked_providers"] == ["libgen-mcp"]


def test_load_policy_config_override_wins_over_env(monkeypatch):
    monkeypatch.setenv(
        POLICY_ENV_VAR,
        json.dumps({"enabled_providers": ["libgen-mcp"], "warn_mcp_temporary_cache": False}),
    )
    policy = load_policy(
        {
            "enabled_providers": ["openlibrary-mcp"],
            "blocked_providers": ["libgen-mcp"],
            "warn_mcp_temporary_cache": True,
        }
    )
    assert policy["enabled_providers"] == ["openlibrary-mcp"]
    assert policy["blocked_providers"] == ["libgen-mcp"]
    assert policy["warn_mcp_temporary_cache"] is True


@pytest.mark.parametrize(
    "raw_env",
    [
        "{not valid json",
        '["list", "not", "dict"]',
        '"just a string"',
        "123",
        "true",
        "null",
        "/nonexistent/path/to/policy.json",
    ],
)
def test_load_policy_rejects_malformed_env(monkeypatch, raw_env):
    monkeypatch.setenv(POLICY_ENV_VAR, raw_env)
    with pytest.raises(ValueError):
        load_policy()


def test_load_policy_rejects_malformed_file_and_non_dict_override(monkeypatch, tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('["not", "an", "object"]', encoding="utf-8")
    monkeypatch.setenv(POLICY_ENV_VAR, str(bad_file))
    with pytest.raises(ValueError):
        load_policy()

    dir_path = tmp_path / "subdir"
    dir_path.mkdir()
    monkeypatch.setenv(POLICY_ENV_VAR, str(dir_path))
    with pytest.raises(ValueError):
        load_policy()

    monkeypatch.delenv(POLICY_ENV_VAR, raising=False)
    with pytest.raises(ValueError):
        load_policy("not-a-dict")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        load_policy({"enabled_providers": "libgen-mcp"})

    with pytest.raises(ValueError):
        load_policy({"require_explicit_confirmation": "yes"})

    with pytest.raises(ValueError):
        load_policy({"default_publish_visibility": "unlisted"})


def test_check_provider_allowed_wildcard_and_blocked_precedence():
    policy = load_policy({"enabled_providers": ["*"], "blocked_providers": ["Bad-MCP"]})

    allowed, reason = check_provider_allowed("libgen-mcp", policy)
    assert allowed is True
    assert "allowed" in reason.casefold()

    blocked, reason_blocked = check_provider_allowed("bad-mcp", policy)
    assert blocked is False
    assert "blocked" in reason_blocked.casefold()


def test_check_provider_allowed_explicit_allowlist_and_blocked_override():
    policy = load_policy(
        {
            "enabled_providers": ["openlibrary-mcp", "libgen-mcp"],
            "blocked_providers": ["libgen-mcp"],
        }
    )

    assert check_provider_allowed("OpenLibrary-MCP", policy)[0] is True
    assert check_provider_allowed("libgen-mcp", policy)[0] is False
    allowed, reason = check_provider_allowed("other-mcp", policy)
    assert allowed is False
    assert "enabled_providers" in reason


def test_check_provider_allowed_rejects_empty_or_wildcard_blocked():
    policy = load_policy()
    assert check_provider_allowed("", policy)[0] is False
    assert check_provider_allowed("   ", policy)[0] is False

    all_blocked = load_policy({"enabled_providers": ["*"], "blocked_providers": ["*"]})
    assert check_provider_allowed("libgen-mcp", all_blocked)[0] is False


def test_build_access_copyright_notice_contains_required_clauses():
    candidate = _sample_candidate()
    policy = load_policy({"warn_mcp_temporary_cache": True})
    notice = build_access_copyright_notice(candidate, policy)

    assert "Open Technical Catalog" in notice
    assert "libgen-mcp" in notice
    assert "Systems Architecture Primer" in notice
    assert "Ada Lovelace, Grace Hopper" in notice
    assert "2nd ed. (2024)" in notice
    assert "9780134685991" in notice
    assert "10.1000/example.42" in notice
    assert "Read-only preview via MCP" in notice
    assert "All rights reserved" in notice

    lowered = notice.casefold()
    assert "does not equal copyright-holder authorization" in lowered
    assert "temporary" in lowered
    assert "cache" in lowered
    assert "model" in lowered


def test_build_access_copyright_notice_respects_cache_warning_flag_and_sparse_fields():
    sparse = {"provider": "openlibrary-mcp", "title": "Sparse Book"}
    policy_no_warn = load_policy({"warn_mcp_temporary_cache": False, "require_explicit_confirmation": False})
    notice = build_access_copyright_notice(sparse, policy_no_warn)

    assert "openlibrary-mcp" in notice
    assert "Sparse Book" in notice
    assert "does not equal copyright-holder authorization" in notice.casefold()
    assert "temporary server cache" not in notice.casefold()


@pytest.mark.parametrize(
    "reply",
    [
        "yes",
        "Yes",
        "  YES! ",
        "y",
        "confirm",
        "confirmed.",
        "I confirm",
        "yes, I confirm.",
        "proceed",
        "i agree",
        "accept",
    ],
)
def test_verify_user_confirmation_accepts_explicit_affirmative(reply):
    candidate = _sample_candidate("libgen-mcp")
    policy = load_policy({"enabled_providers": ["libgen-mcp"]})
    assert verify_user_confirmation(reply, candidate, policy) is True


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "   ",
        "no",
        "n",
        "cancel",
        "abort",
        "stop",
        "maybe",
        "probably",
        "ok?",
        "yes?",
        "confirm?",
        "yes, if it is legal",
        "it is public domain",
        "sure i guess",
        "go ahead maybe",
    ],
)
def test_verify_user_confirmation_rejects_empty_refusal_and_ambiguous(reply):
    candidate = _sample_candidate("libgen-mcp")
    policy = load_policy()
    assert verify_user_confirmation(reply, candidate, policy) is False


def test_verify_user_confirmation_rejects_blocked_provider_even_on_yes():
    candidate = _sample_candidate("blocked-mcp")
    policy = load_policy({"blocked_providers": ["blocked-mcp"]})
    assert verify_user_confirmation("yes", candidate, policy) is False
    assert verify_user_confirmation("I confirm", candidate, policy) is False


def test_verify_user_confirmation_when_confirmation_not_required():
    candidate = _sample_candidate("allowed-mcp")
    policy = load_policy(
        {
            "enabled_providers": ["allowed-mcp"],
            "require_explicit_confirmation": False,
        }
    )
    assert verify_user_confirmation("", candidate, policy) is True
    assert verify_user_confirmation("no", candidate, policy) is False
    assert verify_user_confirmation("cancel", candidate, policy) is False

    blocked = _sample_candidate("other-mcp")
    assert verify_user_confirmation("", blocked, policy) is False


@pytest.mark.parametrize("reply", ["public", "Public", "  public  ", "public.", "PUBLIC!"])
def test_resolve_publish_visibility_locked_unless_policy_allows_and_bare_public(reply):
    locked_policy = load_policy({"allow_public_publish": False})
    assert resolve_publish_visibility(reply, locked_policy) == "private"

    unlocked_policy = load_policy({"allow_public_publish": True})
    assert resolve_publish_visibility(reply, unlocked_policy) == "public"


@pytest.mark.parametrize(
    "reply",
    [
        None,
        "",
        "   ",
        "private",
        "yes",
        "publish",
        "public?",
        "public domain",
        "it is public domain",
        "make it public",
        "public is fine",
    ],
)
def test_resolve_publish_visibility_keeps_non_bare_requests_private(reply):
    unlocked_policy = load_policy({"allow_public_publish": True})
    assert resolve_publish_visibility(reply, unlocked_policy) == "private"
