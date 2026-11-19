"""Static AST and runtime security boundary tests for Mode 2 Search & Read."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.remote.checkpoint import (  # noqa: E402
    FORBIDDEN_PROSE_KEYS as CHECKPOINT_FORBIDDEN_PROSE_KEYS,
    init_remote_session,
    save_remote_session,
    update_chapter_progress,
)
from book_to_skill.remote.coverage import build_coverage_report  # noqa: E402
from book_to_skill.remote.discovery import normalize_work_details  # noqa: E402
from book_to_skill.remote.policy import (  # noqa: E402
    DEFAULT_POLICY,
    POLICY_ENV_VAR,
    check_provider_allowed,
    load_policy,
    resolve_publish_visibility,
    verify_user_confirmation,
)
from book_to_skill.remote.provenance import (  # noqa: E402
    FORBIDDEN_PROSE_KEYS as PROVENANCE_FORBIDDEN_PROSE_KEYS,
    build_remote_provenance,
    render_provenance_markdown,
)
from book_to_skill.remote.reader import (  # noqa: E402
    parse_outline_response,
    read_section_from_pages,
    sanitize_remote_chunk,
)
from tests.remote.mock_mcp import MockMCPServer  # noqa: E402


def _load_scanner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "scan_generated_skill", ROOT_DIR / "tools" / "scan_generated_skill.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scan_generated_skill"] = module
    spec.loader.exec_module(module)
    return module


scanner = _load_scanner()

NETWORK_MODULES = frozenset(
    {
        "urllib",
        "http",
        "requests",
        "httpx",
        "socket",
        "aiohttp",
        "urllib3",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "websocket",
        "websockets",
    }
)


def _collect_ast_imports(py_file: Path) -> list[tuple[str, str]]:
    """Return (kind, full_module_name) for all static and dynamic imports in a file."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imports: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(("import", alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(("from", node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            func_name = None
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name in {"__import__", "import_module"} and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    imports.append(("dynamic", arg0.value))
    return imports


def test_zero_network_imports_across_book_to_skill_package():
    """Verify ZERO modules under book_to_skill/ import outbound network libraries."""
    pkg_root = ROOT_DIR / "book_to_skill"
    remote_root = pkg_root / "remote"
    py_files = sorted(pkg_root.rglob("*.py"))
    assert len(py_files) > 0

    for py_file in py_files:
        rel = py_file.relative_to(ROOT_DIR).as_posix()
        imports = _collect_ast_imports(py_file)
        in_remote = remote_root in py_file.parents

        for kind, mod_name in imports:
            root_mod = mod_name.split(".")[0]
            if in_remote:
                # book_to_skill/remote/ must never import any network or urllib module at all.
                assert root_mod not in NETWORK_MODULES, (
                    f"Forbidden network import ({kind}: {mod_name}) in {rel}"
                )
                assert root_mod != "subprocess", f"Forbidden subprocess import in {rel}"
            else:
                if root_mod == "urllib":
                    # Only pure string-parsing urllib.parse is permitted in epub.py;
                    # urllib.request / urllib.error / bare urllib are strictly forbidden.
                    assert mod_name == "urllib.parse" and rel == "book_to_skill/parsers/epub.py", (
                        f"Forbidden urllib network import ({kind}: {mod_name}) in {rel}"
                    )
                else:
                    assert root_mod not in NETWORK_MODULES, (
                        f"Forbidden network import ({kind}: {mod_name}) in {rel}"
                    )


def test_prompt_injection_unicode_stripped_and_control_tokens_caught_by_scanner(tmp_path: Path):
    """MCP prompt-injection Unicode is stripped by sanitize_remote_chunk and tokens are caught by scanner."""
    # 1. Unicode invisible / bidi / tag-block / annotation injection via MockMCPServer
    mcp = MockMCPServer()
    mcp.set_failure("prompt_injection", "unicode_only")
    raw_pages = list(mcp.iter_section_pages("syn-arch-epub-2", "ch1"))
    assert any("\u200b" in p["text"] or "\u202e" in p["text"] for p in raw_pages)

    chunk_res = sanitize_remote_chunk(raw_pages[0]["text"])
    assert chunk_res["removed_invisible_count"] >= 4
    for invisible in ("\u200b", "\u202e", "\U000e0041", "\ufe0f"):
        assert invisible not in chunk_res["text"]

    section_res = read_section_from_pages(raw_pages)
    assert section_res["sanitized_removed_count"] >= 8
    for invisible in ("\u200b", "\u202e", "\U000e0041", "\ufe0f"):
        assert invisible not in section_res["text"]

    # 2. Control-token / instruction-override payloads caught by tools/scan_generated_skill.py
    mcp.clear_failures()
    mcp.set_failure("prompt_injection", "control_tokens")
    poisoned_pages = list(mcp.iter_section_pages("syn-arch-epub-2", "ch3"))
    poisoned_res = read_section_from_pages(poisoned_pages)

    skill_dir = tmp_path / "poisoned-skill"
    (skill_dir / "chapters").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: poisoned-skill\ndescription: Test skill.\n---\n\n# Poisoned\n",
        encoding="utf-8",
    )
    (skill_dir / "chapters" / "ch03-storage.md").write_text(
        f"# Storage\n\n{poisoned_res['text']}\n",
        encoding="utf-8",
    )

    findings = scanner.scan_generated_skill(skill_dir)
    rule_ids = {f.rule_id for f in findings}
    assert {
        "prompt.ignore_previous",
        "prompt.disregard_system",
        "prompt.system_tag",
        "prompt.tool_call_tag",
        "prompt.fake_system_prefix",
        "tool.exfiltration_shape",
    }.issubset(rule_ids)
    assert scanner.main([str(skill_dir)]) == 1

    # 3. Clean synthesized skill passes scan_generated_skill with exit code 0
    (skill_dir / "chapters" / "ch03-storage.md").write_text(
        "# Storage\n\n- Append-only logs maximize sequential write throughput.\n",
        encoding="utf-8",
    )
    assert scanner.scan_generated_skill(skill_dir) == []
    assert scanner.main([str(skill_dir)]) == 0


def test_session_and_provenance_never_leak_raw_prose(tmp_path: Path):
    """remote_session.json and build_remote_provenance() reject/strip all raw prose fields."""
    sentinel = "SYNTHETIC_PROSE_SENTINEL_NEVER_PERSIST_884422"
    mcp = MockMCPServer()
    details = normalize_work_details(mcp.get_details("syn-arch-epub-2"))
    outline_mode, chapters = parse_outline_response(mcp.read("syn-arch-epub-2", mode="outline"))

    # Inject forbidden prose keys into work/candidate/coverage payloads
    poisoned_work = dict(details)
    for key in CHECKPOINT_FORBIDDEN_PROSE_KEYS | PROVENANCE_FORBIDDEN_PROSE_KEYS:
        poisoned_work[key] = sentinel

    session = init_remote_session(
        poisoned_work,
        provider="libgen-mcp",
        outline_mode=outline_mode,
        chapters=chapters,
        confirmed_by_user=True,
    )
    assert sentinel not in json.dumps(session)

    # Read actual chapter pages through reader and update session
    ch1_res = read_section_from_pages(mcp.iter_section_pages("syn-arch-epub-2", "ch1"))
    update_chapter_progress(session, "ch1", progress=ch1_res)

    workdir = tmp_path / "secure-workdir"
    saved_path = save_remote_session(session, workdir)
    saved_text = saved_path.read_text(encoding="utf-8")
    assert "Resilience begins with explicit failure budgets" not in saved_text
    assert "circuit breakers" not in saved_text
    assert sentinel not in saved_text

    if hasattr(os, "getuid"):
        assert stat.S_IMODE(workdir.stat().st_mode) == 0o700
        assert stat.S_IMODE(saved_path.stat().st_mode) == 0o600

    # Direct tampering of session dict with any forbidden prose key must fail closed
    for key in sorted(CHECKPOINT_FORBIDDEN_PROSE_KEYS):
        tampered = json.loads(saved_text)
        tampered["chapters"][0][key] = sentinel
        with pytest.raises(ValueError, match="raw prose"):
            save_remote_session(tampered, tmp_path / f"tamper-{key}")

    # Provenance builder strips/ignores prose keys across candidate, session, and coverage
    poisoned_session = json.loads(saved_text)
    poisoned_session["text"] = sentinel
    poisoned_session["work"]["raw_text"] = sentinel
    poisoned_coverage = build_coverage_report(poisoned_session)
    poisoned_coverage["excerpt"] = sentinel
    poisoned_coverage["raw_pages"] = [sentinel]

    policy = load_policy()
    provenance = build_remote_provenance(
        poisoned_work,
        poisoned_session,
        policy,
        coverage=poisoned_coverage,
    )
    prov_json = json.dumps(provenance)
    assert sentinel not in prov_json
    assert "Resilience begins with explicit failure budgets" not in prov_json

    prov_md = render_provenance_markdown(provenance)
    assert sentinel not in prov_md
    assert "Resilience begins with explicit failure budgets" not in prov_md


def test_policy_defaults_enforce_private_and_configurable_provider_blocklists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Default policy enforces --private visibility and supports blocklists without code edits."""
    monkeypatch.delenv(POLICY_ENV_VAR, raising=False)
    default_policy = load_policy()
    assert default_policy == DEFAULT_POLICY
    assert default_policy["default_publish_visibility"] == "private"
    assert default_policy["allow_public_publish"] is False
    assert default_policy["require_explicit_confirmation"] is True

    # Even explicit 'public' requests stay private under default policy
    assert resolve_publish_visibility("public", default_policy) == "private"
    assert resolve_publish_visibility("PUBLIC", default_policy) == "private"

    mcp = MockMCPServer(provider_name="mirror-blocked-mcp")
    candidate = normalize_work_details(mcp.get_details("syn-arch-epub-2"), provider="mirror-blocked-mcp")
    session = init_remote_session(
        candidate,
        provider="mirror-blocked-mcp",
        outline_mode="outline",
        chapters=[{"index": 1, "section_id": "ch1", "title": "Ch1"}],
        confirmed_by_user=True,
    )
    prov = build_remote_provenance(
        candidate,
        session,
        default_policy,
        requested_visibility="public",
    )
    assert prov["publish_visibility"] == "private"

    # Configurable provider blocklist via env JSON file (no pipeline code changes)
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(
        json.dumps(
            {
                "enabled_providers": ["trusted-mcp", "mirror-blocked-mcp"],
                "blocked_providers": ["mirror-blocked-mcp"],
                "allow_public_publish": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(POLICY_ENV_VAR, str(policy_file))
    configured = load_policy()

    allowed_blocked, reason_blocked = check_provider_allowed("mirror-blocked-mcp", configured)
    assert allowed_blocked is False
    assert "blocked" in reason_blocked.casefold()
    assert verify_user_confirmation("yes", candidate, configured) is False

    allowed_trusted, _ = check_provider_allowed("trusted-mcp", configured)
    assert allowed_trusted is True

    allowed_other, reason_other = check_provider_allowed("unlisted-mcp", configured)
    assert allowed_other is False
    assert "enabled_providers" in reason_other

    # Inline env JSON also configures blocklist dynamically
    monkeypatch.setenv(
        POLICY_ENV_VAR,
        json.dumps({"enabled_providers": ["*"], "blocked_providers": ["*"]}),
    )
    lockdown = load_policy()
    assert check_provider_allowed("trusted-mcp", lockdown)[0] is False
