"""Regression test: keep bytecode out of the deployed skill, from entry points.

When book-to-skill is installed as an agent skill, the skill *is* the source
tree — it is cloned or unpacked into `~/.config/opencode/skills/<name>/` (or
another host root) and executed from there. Any `__pycache__` written on first
run ends up shipped inside the skill: extra files to scan, noise in diffs, and
`__pycache__/*.pyc` showing up wherever the skill is published or shared.

The agent invoking the skill does not set PYTHONDONTWRITEBYTECODE, so the guard
has to live in the entry points themselves, before the package is imported.

The guard does NOT belong at import time in a library module: a host process
that merely does `import book_to_skill` must not have its global
`sys.dont_write_bytecode` flipped underneath it. `if __name__ == "__main__":`
is false for such an import, which is why the policy is wrapped in it.

Two failure modes this test must reject, both fixed here:
  * a subprocess that crashes before doing anything — the old test discarded
    the return code, so an entry point that immediately raised
    `SystemExit(1)` still reported "1 passed";
  * a vacuous pass from an empty output — every run now asserts the tool
    actually produced its documented banner/usage line.

Bytecode is measured in an isolated deployment copy, never by deleting files
from the developer's working tree.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent

# The standalone entry points, mapped to a line each one must actually print
# when invoked with `--help`. Kept explicit on purpose: if a new entry point
# appears, this list — and the guard it asserts — must be revisited, and
# `test_entry_point_list_still_matches_the_source_tree` says so.
#
# `extract.py`/`cli.py` emit the attribution banner on stderr (see
# `utils.print_intro`), so the presence check reads stdout + stderr; the point
# is that output is non-empty and expected, not that it lands on a stream.
ENTRY_POINTS = {
    "scripts/extract.py": "book-to-skill · turns a document into a structured agent skill",
    "tools/scan_generated_skill.py": "usage: scan_generated_skill.py [-h] path",
    "tools/discovery_tax.py": (
        "usage: discovery_tax.py [-h] --full-text FULL_TEXT [--skill-dir SKILL_DIR]"
    ),
    "book_to_skill/cli.py": "book-to-skill · turns a document into a structured agent skill",
}

# Everything the four entry points import. Copied into the isolated deployment
# so the runs under test resolve `book_to_skill` to the copy, not to the
# developer's checkout.
PAYLOAD = ("book_to_skill", "scripts", "tools")

# The exact marker the policy must sit inside.
MAIN_GUARD = 'if __name__ == "__main__":'

# Directories that never contribute to the payload and are not worth walking.
_WALK_SKIP = {".git", ".venv", "venv", "node_modules", ".tox"}


def _iter_source_files(root: Path = REPO_ROOT):
    """Yield candidate files, pruning whole directories we never care about."""
    for path in root.rglob("*"):
        if _WALK_SKIP & set(path.relative_to(root).parts):
            continue
        yield path


def _ignore_bytecode(_directory: str, names: list[str]) -> list[str]:
    """`shutil.copytree` ignore fn: never seed the copy with bytecode."""
    return [name for name in names if name == "__pycache__" or name.endswith(".pyc")]


@pytest.fixture()
def deployed(tmp_path: Path) -> Path:
    """An isolated deployment copy of the skill payload, free of bytecode.

    The copy — not the developer's source tree — is where artifacts are
    measured, so this test can never delete or write into the checkout it
    lives in.
    """
    dest = tmp_path / "skill"
    dest.mkdir()
    for name in PAYLOAD:
        shutil.copytree(REPO_ROOT / name, dest / name, ignore=_ignore_bytecode)
    return dest


def _env() -> dict:
    """Environment with inherited bytecode protection deliberately stripped.

    The guard must hold for an agent that simply runs the tool, so we also drop
    any cache-prefix override that would relocate (rather than suppress) `.pyc`
    writes out of the measured tree.
    """
    return {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"}
    }


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


def _run_entry(deployed: Path, entry: str, expected: str) -> subprocess.CompletedProcess:
    """Run one entry point and prove it really executed.

    Both halves of the contract are asserted through this one helper, so a
    deliberately broken entry point cannot slip past: the return code must be
    zero AND the expected output line must be present. Discarding the return
    code, or accepting empty output, is a failure — see the negative control.
    """
    env = _env()
    env["PYTHONPATH"] = str(deployed)
    completed = _run(
        [sys.executable, str(deployed / entry), "--help"], cwd=deployed, env=env
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, (
        f"{entry} exited {completed.returncode}; it must run successfully "
        f"(--help). stderr: {completed.stderr.strip()[:300]}"
    )
    assert expected in output, (
        f"{entry} did not produce its expected output {expected!r}; "
        f"stdout={completed.stdout.strip()[:200]!r} "
        f"stderr={completed.stderr.strip()[:200]!r}"
    )
    return completed


def _bytecode(deployed: Path) -> tuple[list[str], list[str]]:
    """Bytecode artifacts in the deployment: `.pyc` files and `__pycache__`."""
    pyc = sorted(str(p.relative_to(deployed)) for p in deployed.rglob("*.pyc") if p.is_file())
    caches = sorted(
        str(p.relative_to(deployed)) for p in deployed.rglob("__pycache__") if p.is_dir()
    )
    return pyc, caches


@pytest.mark.parametrize("entry", list(ENTRY_POINTS))
def test_entry_point_writes_no_bytecode(deployed, entry):
    script = deployed / entry
    assert script.is_file(), f"missing entry point: {entry}"

    _run_entry(deployed, entry, ENTRY_POINTS[entry])

    pyc, caches = _bytecode(deployed)
    assert pyc == [], f"{entry} left build artifacts in the deployment: {pyc[:5]}"
    assert caches == [], f"{entry} left __pycache__ in the deployment: {caches[:5]}"


def test_entry_points_set_the_policy_before_importing_the_package():
    """The guard must live in each entry point, ahead of the package import."""
    for entry in ENTRY_POINTS:
        lines = (REPO_ROOT / entry).read_text(encoding="utf-8").splitlines()
        assert any(line.strip() == MAIN_GUARD for line in lines), (
            f"{entry} has no `{MAIN_GUARD}` guard, so its `dont_write_bytecode` "
            "policy would also fire for an embedding import"
        )
        guard_at = next(i for i, line in enumerate(lines) if line.strip() == MAIN_GUARD)
        import_at = next(
            i
            for i, line in enumerate(lines)
            if line.lstrip().startswith(("from book_to_skill", "import book_to_skill"))
        )
        assert "sys.dont_write_bytecode = True" in "\n".join(lines[guard_at:import_at]), (
            f"{entry} must set sys.dont_write_bytecode inside its `__main__` "
            "guard and before importing book_to_skill"
        )


def test_entry_point_list_still_matches_the_source_tree():
    """Guard against the list going stale as the package grows."""
    found = set()
    for py in _iter_source_files():
        if py.suffix != ".py":
            continue
        try:
            lines = py.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        imports_package = any(
            line.lstrip().startswith(("from book_to_skill", "import book_to_skill"))
            for line in lines
        )
        if not imports_package:
            continue
        # A module that imports the package *and* is designed to be run directly
        # is an entry point: it must carry the policy. `def main(` alone is not
        # enough — `utils.py` is a pure library module and must NOT be listed.
        if any(line.strip() == MAIN_GUARD for line in lines):
            found.add(py.relative_to(REPO_ROOT).as_posix())

    # `__main__.py`/`__init__.py` cannot be guarded from inside the package:
    # Python compiles them before any of our code runs. They are excluded here
    # and instead SKILL.md must never invoke `python -m book_to_skill`.
    found -= {"book_to_skill/__main__.py", "book_to_skill/__init__.py"}

    assert found == set(ENTRY_POINTS), (
        "entry points changed; update ENTRY_POINTS and make sure every one sets "
        f"sys.dont_write_bytecode. Diff: {sorted(found ^ set(ENTRY_POINTS))}"
    )


def test_importing_the_library_does_not_mutate_the_embedding_process(deployed):
    """Importing the package must not flip `sys.dont_write_bytecode`.

    This is the direct regression guard for the policy leaking out of a library
    import: an embedding host that imports book-to-skill keeps its own global
    interpreter state. Run in a subprocess whose CWD/PYTHONPATH are the isolated
    copy, so it cannot silently import the developer's checkout instead.
    """
    env = _env()
    env["PYTHONPATH"] = str(deployed)
    completed = _run(
        [
            sys.executable,
            "-c",
            (
                "import sys;"
                " sys.dont_write_bytecode = False;"
                " import book_to_skill, book_to_skill.utils, book_to_skill.cli;"
                f" assert book_to_skill.__file__.startswith({str(deployed)!r}),"
                " book_to_skill.__file__;"
                " print(sys.dont_write_bytecode)"
            ),
        ],
        cwd=deployed,
        env=env,
    )
    assert completed.returncode == 0, (
        f"import probe failed ({completed.returncode}): {completed.stderr.strip()[:300]}"
    )
    assert completed.stdout.strip() == "False", (
        "importing book_to_skill mutated the embedding process: "
        f"sys.dont_write_bytecode is {completed.stdout.strip()!r}"
    )


def test_negative_control_broken_entry_point_is_reported_as_failure(deployed):
    """Prove the assertions above can fail — the old test could not.

    A deliberately broken entry point (body immediately raises SystemExit(1),
    printing nothing) is run through the *same* helper the real tests use. The
    helper must report failure rather than pass on a discarded return code, so
    `pytest.raises(AssertionError)` here is the guarantee that "returncode is
    discarded" is no longer possible.
    """
    broken = deployed / "scripts" / "_negative_control_entry.py"
    broken.write_text("raise SystemExit(1)\n", encoding="utf-8")

    env = _env()
    env["PYTHONPATH"] = str(deployed)
    raw = _run([sys.executable, str(broken)], cwd=deployed, env=env)
    assert raw.returncode != 0, "negative control must actually fail to run"
    assert raw.stdout.strip() == "", "negative control must produce no output"

    with pytest.raises(AssertionError):
        _run_entry(
            deployed,
            "scripts/_negative_control_entry.py",
            ENTRY_POINTS["scripts/extract.py"],
        )
