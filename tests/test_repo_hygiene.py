"""Regression test: build artifacts must never be tracked in the repository."""

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=30,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"git unavailable: {exc}")


def _tracked_files() -> list[str]:
    """Every path tracked in this repository.

    Uses -z because `git ls-files` otherwise quotes non-ASCII paths
    (`"caf\\303\\251/stale.pyc"`), which would silently defeat the suffix check
    below and let the test pass while bytecode is tracked.
    """
    toplevel = _git("rev-parse", "--show-toplevel")
    if toplevel.returncode != 0:
        pytest.skip("not a git checkout (e.g. installed sdist)")
    if Path(toplevel.stdout.strip()).resolve() != REPO_ROOT:
        # Vendored inside an unrelated repo: `git ls-files` would answer for that
        # repo, so an empty result would be a vacuous pass rather than a real one.
        pytest.skip("REPO_ROOT is not the root of the enclosing git repository")

    listed = _git("ls-files", "-z")
    if listed.returncode != 0:
        pytest.skip("not a git checkout (e.g. installed sdist)")
    return [path for path in listed.stdout.split("\0") if path]


def test_no_compiled_bytecode_is_tracked():
    """`.gitignore` lists *.pyc and __pycache__/, but ignore rules do not untrack
    files already committed. A stale .pyc shipped in the repo is build noise at
    best and a supply-chain smell at worst, since bytecode is not reviewable in a
    diff."""
    offenders = [
        path
        for path in _tracked_files()
        if path.endswith(".pyc") or "__pycache__/" in path
    ]
    assert offenders == [], (
        "compiled bytecode is tracked in git: "
        + ", ".join(offenders)
        + " — remove with `git rm --cached <path>`"
    )
