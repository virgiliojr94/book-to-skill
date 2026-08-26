"""Regression checks for the repository-local Factory integration."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_hook(command: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        ["bash", str(ROOT / ".claude/hooks/block-merge.sh")],
        cwd=ROOT,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )


def test_factory_hook_blocks_merge_and_allows_read_only_status() -> None:
    blocked = run_hook("git merge feature")
    assert blocked.returncode == 2
    assert "BLOCKED by factory hook" in blocked.stderr

    allowed = run_hook("git status --short")
    assert allowed.returncode == 0
    assert allowed.stderr == ""


def test_factory_shell_scripts_have_valid_bash_syntax() -> None:
    scripts = [
        ROOT / ".claude/hooks/block-merge.sh",
        ROOT / ".claude/scripts/gates.sh",
        ROOT / ".factory/scripts/bootstrap-github.sh",
        ROOT / ".factory/scripts/doctor.sh",
        ROOT / ".factory/scripts/prove-test.sh",
    ]
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(script)], cwd=ROOT, check=False)
        assert result.returncode == 0, script


def test_factory_charter_declares_ready_policy() -> None:
    charter = (ROOT / "docs/factory/CHARTER.md").read_text(encoding="utf-8")
    for field in (
        "CHARTER_STATUS: ready",
        "TIER: oss",
        "LOAD_BEARING:",
        "AUTOMATABLE:",
        "STOP_IF:",
        "DEFINITION_OF_DONE:",
        "PROTECTED_PATHS:",
        "REVIEW_LIMIT: 3",
    ):
        assert field in charter
    assert "<PROJECT NAME>" not in charter
