"""Offline provider policy and access/copyright confirmation gate for remote MCP workflows."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

POLICY_ENV_VAR = "BOOK_TO_SKILL_REMOTE_POLICY"

DEFAULT_POLICY: dict[str, Any] = {
    "enabled_providers": ["*"],
    "blocked_providers": [],
    "require_explicit_confirmation": True,
    "default_publish_visibility": "private",
    "allow_public_publish": False,
    "warn_mcp_temporary_cache": True,
}

_EXPLICIT_AFFIRMATIVES = frozenset(
    {
        "y",
        "yes",
        "confirm",
        "confirmed",
        "i confirm",
        "yes i confirm",
        "yes confirm",
        "proceed",
        "yes proceed",
        "confirm and proceed",
        "agree",
        "i agree",
        "yes i agree",
        "accept",
        "i accept",
        "approve",
        "approved",
        "i approve",
        "continue",
        "yes continue",
    }
)

_EXPLICIT_REFUSALS = frozenset(
    {
        "n",
        "no",
        "nope",
        "cancel",
        "abort",
        "stop",
        "decline",
        "deny",
        "refuse",
        "skip",
        "false",
        "0",
    }
)

__all__ = [
    "DEFAULT_POLICY",
    "POLICY_ENV_VAR",
    "build_access_copyright_notice",
    "check_provider_allowed",
    "load_policy",
    "resolve_publish_visibility",
    "verify_user_confirmation",
]


def _copy_default_policy() -> dict[str, Any]:
    return {
        "enabled_providers": list(DEFAULT_POLICY["enabled_providers"]),
        "blocked_providers": list(DEFAULT_POLICY["blocked_providers"]),
        "require_explicit_confirmation": DEFAULT_POLICY["require_explicit_confirmation"],
        "default_publish_visibility": DEFAULT_POLICY["default_publish_visibility"],
        "allow_public_publish": DEFAULT_POLICY["allow_public_publish"],
        "warn_mcp_temporary_cache": DEFAULT_POLICY["warn_mcp_temporary_cache"],
    }


def _parse_policy_json_text(raw_text: str, source_label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {source_label}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{source_label} must decode to a JSON object (dict), got {type(parsed).__name__}")
    return parsed


def _load_env_policy() -> dict[str, Any]:
    raw_env = os.environ.get(POLICY_ENV_VAR, "").strip()
    if not raw_env:
        return {}

    if raw_env.startswith("{") or raw_env.startswith("["):
        return _parse_policy_json_text(raw_env, POLICY_ENV_VAR)

    candidate_path = Path(raw_env).expanduser()
    if candidate_path.exists():
        if not candidate_path.is_file():
            raise ValueError(f"{POLICY_ENV_VAR} path is not a regular file: {candidate_path}")
        try:
            file_text = candidate_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"Unable to read {POLICY_ENV_VAR} file {candidate_path}: {exc}") from exc
        return _parse_policy_json_text(file_text, f"{POLICY_ENV_VAR} ({candidate_path})")

    try:
        parsed = json.loads(raw_env)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{POLICY_ENV_VAR} is neither valid JSON nor an existing policy file: {raw_env!r}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{POLICY_ENV_VAR} must decode to a JSON object (dict), got {type(parsed).__name__}")
    return parsed


def _normalize_provider_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Policy field '{field_name}' must be a list of strings, got {type(value).__name__}")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Policy field '{field_name}' must contain only non-empty strings")
        normalized.append(item.strip())
    return normalized


def _validate_and_normalize_policy(policy: dict[str, Any]) -> dict[str, Any]:
    validated = dict(policy)
    validated["enabled_providers"] = _normalize_provider_list(
        policy.get("enabled_providers"), "enabled_providers"
    )
    validated["blocked_providers"] = _normalize_provider_list(
        policy.get("blocked_providers"), "blocked_providers"
    )

    for bool_field in (
        "require_explicit_confirmation",
        "allow_public_publish",
        "warn_mcp_temporary_cache",
    ):
        val = policy.get(bool_field)
        if not isinstance(val, bool):
            raise ValueError(f"Policy field '{bool_field}' must be a bool, got {type(val).__name__}")

    visibility = policy.get("default_publish_visibility")
    if not isinstance(visibility, str) or visibility not in ("private", "public"):
        raise ValueError("Policy field 'default_publish_visibility' must be 'private' or 'public'")

    return validated


def load_policy(config_override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load remote provider policy from defaults, optional env JSON/file, and override dict."""
    if config_override is not None and not isinstance(config_override, dict):
        raise ValueError(f"config_override must be a dict or None, got {type(config_override).__name__}")

    merged = _copy_default_policy()
    merged.update(_load_env_policy())
    if config_override:
        merged.update(config_override)
    return _validate_and_normalize_policy(merged)


def check_provider_allowed(provider: str, policy: dict[str, Any]) -> tuple[bool, str]:
    """Check whether a remote MCP provider is allowed by policy.

    `blocked_providers` takes precedence over `enabled_providers`.
    `"*"` in `enabled_providers` permits any non-blocked provider.
    """
    if not isinstance(policy, dict):
        raise ValueError(f"policy must be a dict, got {type(policy).__name__}")
    if not isinstance(provider, str) or not provider.strip():
        return False, "Provider name is empty or missing."

    name = provider.strip()
    key = name.casefold()

    raw_blocked = policy.get("blocked_providers", DEFAULT_POLICY["blocked_providers"])
    raw_enabled = policy.get("enabled_providers", DEFAULT_POLICY["enabled_providers"])
    if not isinstance(raw_blocked, (list, tuple)) or not isinstance(raw_enabled, (list, tuple)):
        raise ValueError("Policy provider lists must be lists of strings")

    blocked = {str(item).strip().casefold() for item in raw_blocked if isinstance(item, str) and item.strip()}
    enabled = {str(item).strip().casefold() for item in raw_enabled if isinstance(item, str) and item.strip()}

    if "*" in blocked or key in blocked:
        return False, f"Provider '{name}' is blocked by policy."
    if "*" in enabled:
        return True, f"Provider '{name}' is allowed by wildcard policy."
    if key in enabled:
        return True, f"Provider '{name}' is explicitly allowed by policy."
    return False, f"Provider '{name}' is not in enabled_providers."


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _format_authors(authors: Any) -> str:
    if isinstance(authors, (list, tuple)):
        cleaned = [str(a).strip() for a in authors if str(a).strip()]
        return ", ".join(cleaned) if cleaned else "Unknown"
    cleaned_single = _clean_text(authors)
    return cleaned_single or "Unknown"


def _format_identifiers(identifiers: Any) -> tuple[str, str]:
    if not isinstance(identifiers, dict):
        return "None", "None"
    raw_isbn = identifiers.get("isbn")
    if isinstance(raw_isbn, (list, tuple)):
        isbns = [str(i).strip() for i in raw_isbn if str(i).strip()]
        isbn_text = ", ".join(isbns) if isbns else "None"
    else:
        isbn_text = _clean_text(raw_isbn) or "None"
    doi_text = _clean_text(identifiers.get("doi")) or "None"
    return isbn_text, doi_text


def build_access_copyright_notice(candidate: dict[str, Any], policy: dict[str, Any]) -> str:
    """Build the access, copyright, and temporary-cache notice for a candidate work."""
    if not isinstance(candidate, dict):
        raise ValueError(f"candidate must be a dict, got {type(candidate).__name__}")
    if not isinstance(policy, dict):
        raise ValueError(f"policy must be a dict, got {type(policy).__name__}")

    provider = _clean_text(candidate.get("provider")) or "unknown"
    source_name = _clean_text(candidate.get("source_name")) or provider
    source_line = source_name if source_name == provider else f"{source_name} (provider: {provider})"

    title = _clean_text(candidate.get("title")) or "Unknown title"
    authors = _format_authors(candidate.get("authors"))
    edition = _clean_text(candidate.get("edition")) or "Unspecified"
    year = candidate.get("year")
    edition_line = f"{edition} ({year})" if year not in (None, "") else edition

    isbn_text, doi_text = _format_identifiers(candidate.get("identifiers"))
    access_info = _clean_text(candidate.get("access_info")) or "Unknown / not specified"
    license_info = _clean_text(candidate.get("license_info")) or "Unknown / not specified"

    lines = [
        "Remote Work Access & Copyright Notice",
        f"- Source / Provider: {source_line}",
        f"- Title: {title}",
        f"- Authors: {authors}",
        f"- Edition: {edition_line}",
        f"- Identifiers: ISBN: {isbn_text} | DOI: {doi_text}",
        f"- Access terms: {access_info}",
        f"- License: {license_info}",
        (
            "Important: User confirmation does NOT equal copyright-holder authorization "
            "and does not grant redistribution rights. Verify that you are permitted to "
            "access and process this work."
        ),
    ]

    if policy.get("warn_mcp_temporary_cache", True) is True:
        lines.append(
            "Technical notice: MCP `read` may use a temporary server cache and "
            "transmit extracted text chunks to the model context. Raw fragments are "
            "not saved permanently locally."
        )

    if policy.get("require_explicit_confirmation", True) is True:
        lines.append("Reply explicitly with 'confirm' or 'yes' to proceed, or 'cancel' to abort.")

    return "\n".join(lines)


def verify_user_confirmation(reply: str, candidate: dict[str, Any], policy: dict[str, Any]) -> bool:
    """Verify explicit affirmative user consent and that the candidate provider is allowed."""
    if not isinstance(candidate, dict) or not isinstance(policy, dict):
        return False

    provider = candidate.get("provider", "")
    allowed, _ = check_provider_allowed(provider if isinstance(provider, str) else "", policy)
    if not allowed:
        return False

    require_confirmation = policy.get("require_explicit_confirmation", True)
    if not isinstance(require_confirmation, bool):
        return False

    if reply is None:
        return not require_confirmation
    if not isinstance(reply, str):
        return False

    if "?" in reply:
        return False

    cleaned = reply.strip().rstrip(".!").strip()
    normalized = re.sub(r"\s+", " ", cleaned.replace(",", "")).strip().casefold()

    if normalized in _EXPLICIT_REFUSALS:
        return False
    if not require_confirmation:
        return True
    if not normalized:
        return False
    return normalized in _EXPLICIT_AFFIRMATIVES


def resolve_publish_visibility(requested: str | None, policy: dict[str, Any]) -> str:
    """Resolve repository publish visibility, strictly locking to 'private' by default.

    Returns 'public' ONLY when policy['allow_public_publish'] is True AND
    `requested` is the bare word 'public' (ignoring surrounding whitespace/case/punctuation,
    excluding '?'). All other inputs strictly return 'private'.
    """
    if not isinstance(policy, dict) or policy.get("allow_public_publish") is not True:
        return "private"
    if not isinstance(requested, str) or "?" in requested:
        return "private"
    normalized = requested.strip().strip(".!,:;").strip().casefold()
    if normalized == "public":
        return "public"
    return "private"
