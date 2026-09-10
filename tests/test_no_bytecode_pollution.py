"""Regression test: running the tools must not leave bytecode in the source tree.

When book-to-skill is installed as an agent skill, the skill *is* the source
tree — it is cloned or unpacked into `~/.config/opencode/skills/<name>/` (or
another host root) and executed from there. Any `__pycache__` written on first
run ends up shipped inside the skill: extra files to scan, noise in diffs, and
`__pycache__/*.pyc` showing up wherever the skill is published or shared.

The agent invoking the skill does not set PYTHONDONTWRITEBYTECODE, so the guard
has to live in the entry points themselves, before the package is imported.
"""

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

# Every module that (a) imports `book_to_skill` and (b) can be run directly.
# Kept explicit on purpose: if a new entry point appears, this list — and the
# guard it asserts — must be revisited, and the test says so.
ENTRY_POINTS = [
    "scripts/extract.py",
    "tools/scan_generated_skill.py",
    "tools/discovery_tax.py",
    "book_to_skill/cli.py",
    "book_to_skill/utils.py",
]


# Directories that never contribute to the payload and are not worth walking.
# `__pycache__` is deliberately NOT listed: it is exactly what we hunt for, and
# excluding it here would also hide the `.pyc` files inside it (their path
# contains a `__pycache__` part), making every assertion vacuously true.
_WALK_SKIP = {".git", ".venv", "venv", "node_modules", ".tox"}


def _iter_source_files():
    """Yield candidate files, pruning whole directories we never care about."""
    for path in REPO_ROOT.rglob("*"):
        if _WALK_SKIP & set(path.relative_to(REPO_ROOT).parts):
            continue
        yield path


def _clean() -> None:
    """Remove bytecode written by test runs or earlier imports."""
    for path in list(REPO_ROOT.rglob("__pycache__")):
        if _WALK_SKIP & set(path.relative_to(REPO_ROOT).parts):
            continue
        if "tests" in path.relative_to(REPO_ROOT).parts:
            continue
        for child in path.iterdir():
            child.unlink(missing_ok=True)
        path.rmdir()
    for pyc in REPO_ROOT.rglob("*.pyc"):
        rel = pyc.relative_to(REPO_ROOT)
        if _WALK_SKIP & set(rel.parts) or "tests" in rel.parts:
            continue
        pyc.unlink(missing_ok=True)


def _artifacts() -> list[str]:
    """Bytecode artifacts that would ship inside the skill."""
    # Bytecode for the test suite itself is written by pytest when it imports
    # this module; it is never part of the skill payload, and counting it would
    # make the pre-check fail for a reason unrelated to the code under test.
    return sorted(
        str(p.relative_to(REPO_ROOT))
        for p in _iter_source_files()
        if p.is_file() and p.suffix == ".pyc"
        and "tests" not in p.relative_to(REPO_ROOT).parts
    )


def _run(argv: list[str], *, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


@pytest.fixture()
def clean_tree():
    """Start from a tree free of bytecode, and leave it that way.

    Cleaning rather than asserting on entry matters: other tests import these
    same modules, so by the time this one runs the tree legitimately contains
    bytecode. We only care what *this* test's entry point writes.
    """
    _clean()
    yield
    _clean()


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_entry_point_writes_no_bytecode(clean_tree, entry):
    script = REPO_ROOT / entry
    assert script.is_file(), f"missing entry point: {entry}"

    # Deliberately strip any inherited protection: the guard must hold for an
    # agent that simply runs the tool.
    env = {k: v for k, v in __import__("os").environ.items()
           if k != "PYTHONDONTWRITEBYTECODE"}
    env["PYTHONPATH"] = str(REPO_ROOT)

    argv = [sys.executable, str(script)]
    if entry != "book_to_skill/utils.py":
        argv.append("--help")

    _run(argv, cwd=REPO_ROOT, env=env)

    dirty = _artifacts()

    # Make sure we exercised a real import rather than a path that bailed out
    # early (a crash before importing the package would leave no bytecode and
    # pass vacuously).
    if entry != "book_to_skill/utils.py":
        probe = _run(argv, cwd=REPO_ROOT, env=env)
        assert probe.returncode == 0, (
            f"{entry} exited {probe.returncode}; the test would pass only "
            f"because the import never happened: {probe.stderr.strip()[:200]}"
        )

    assert dirty == [], f"{entry} left build artifacts: {dirty[:5]}"


def test_entry_point_list_still_matches_the_source_tree(clean_tree):
    """Guard against the list going stale as the package grows."""
    found = set()
    for py in _iter_source_files():
        if py.suffix != ".py":
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        imports_package = any(
            line.lstrip().startswith(("from book_to_skill", "import book_to_skill"))
            for line in text.splitlines()
        )
        if not imports_package:
            continue
        if "__main__" in text or "argparse" in text or "def main(" in text:
            found.add(py.relative_to(REPO_ROOT).as_posix())

    # `__main__.py`/`__init__.py` cannot be guarded from inside the package:
    # Python compiles them before any of our code runs. They are excluded here
    # and instead SKILL.md must never invoke `python -m book_to_skill`.
    found -= {"book_to_skill/__main__.py", "book_to_skill/__init__.py"}

    assert found == set(ENTRY_POINTS), (
        "entry points changed; update ENTRY_POINTS and make sure every one sets "
        f"sys.dont_write_bytecode. Diff: {sorted(found ^ set(ENTRY_POINTS))}"
    )
