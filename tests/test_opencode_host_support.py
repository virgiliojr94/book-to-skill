"""OpenCode host-discovery contract in the converter spec.

OpenCode has no project-trust gate (unlike Hermes Agent): it discovers skills
automatically by walking up from the working directory to the git worktree, and
it reads `~/.config/opencode/skills`, `~/.agents/skills` and `~/.claude/skills`
as global roots. So these tests cover path discovery plus the guarantee that
OpenCode does not pick up another host's directory — not trust behavior.
"""

import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")

# Candidate bashes, most reliable first. On Windows a bare "bash" cannot be
# used: CreateProcess resolves bare names against the system directory before
# PATH, so it always picks C:\Windows\System32\bash.exe — a WSL stub that exits
# 255 when no distro is installed, even though a perfectly good Git bash sits
# elsewhere. So we keep absolute candidates and invoke those directly.
_BASH_CANDIDATES = ["bash", "/usr/bin/bash", "/bin/bash"]


def _bash_candidates():
    cands = list(_BASH_CANDIDATES)
    if os.name == "nt":
        # Git for Windows ships a real bash next to git.exe (cmd/git.exe ->
        # ../../bin/bash.exe). Also honour the same override OpenCode uses.
        override = os.environ.get("OPENCODE_GIT_BASH_PATH")
        if override:
            cands.insert(0, override)
        git = shutil.which("git")
        if git:
            cands.insert(
                0,
                str(Path(git).resolve().parent.parent / "bin" / "bash.exe"),
            )
    return cands


def _find_bash():
    """Return a bash that actually executes `bash -c true`, or None.

    Detection must agree with execution, so every candidate is invoked exactly
    the way the tests will invoke it: `bash -c <script>`.
    """
    for cand in _bash_candidates():
        if not (os.path.isabs(cand) or shutil.which(cand)):
            continue
        try:
            probe = subprocess.run(
                [cand, "-c", "true"],
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return cand
    return None


BASH = _find_bash()

# The probe block in SKILL.md is a bash snippet; on hosts with no working bash
# at all the discovery contract cannot be exercised.
pytestmark = pytest.mark.skipif(BASH is None, reason="no working bash available")


def _extract_probe_script():
    start = SKILL.index('SCRIPT_PATH=""')
    end = SKILL.index('\nif [ -z "$SCRIPT_PATH" ]', start)
    return SKILL[start:end] + '\nprintf "%s" "$SCRIPT_PATH"\n'


def _env(tmp_path, home):
    env = os.environ.copy()
    env.update({"HOME": str(home)})
    env.pop("HERMES_AGENT", None)
    return env


def _git_project(tmp_path, name="project"):
    project = tmp_path / name
    project.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    return project


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _run_probe(cwd, env):
    # Use the very bash `_find_bash()` validated, so detection and execution can
    # never disagree.
    result = subprocess.run(
        [BASH, "-c", _extract_probe_script()],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _to_host_path(raw):
    """Convert a path produced by bash into one the host Python understands.

    Git bash (MSYS) reports Windows paths in its own form — `$HOME` comes back
    as `/tmp/...` or `/c/Users/...` rather than `C:/Users/...`. Comparing that
    against a `pathlib` path fails for reasons that have nothing to do with the
    code under test, so normalise through `cygpath -w` when it is available.
    """
    if os.name != "nt" or not raw.startswith("/"):
        return raw
    try:
        out = subprocess.run(
            [BASH, "-lc", "cygpath -w -- " + shlex.quote(raw)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return raw
    if out.returncode != 0:
        return raw
    return out.stdout.strip()


def _resolve(cwd, raw):
    selected = Path(_to_host_path(raw))
    if not selected.is_absolute():
        selected = cwd / selected
    return selected.resolve()


def test_opencode_is_named_as_supported_host():
    assert "OpenCode" in SKILL


@pytest.mark.parametrize(
    "layout",
    ["personal-native", "personal-agents", "personal-claude", "project-opencode"],
)
def test_opencode_extractor_probe_discovers_supported_layouts(tmp_path, layout):
    home = tmp_path / "home"
    project = _git_project(tmp_path)
    nested = project / "src" / "nested"
    nested.mkdir(parents=True)

    roots = {
        "personal-native": home / ".config" / "opencode" / "skills" / "book-to-skill",
        "personal-agents": home / ".agents" / "skills" / "book-to-skill",
        "personal-claude": home / ".claude" / "skills" / "book-to-skill",
        "project-opencode": project / ".opencode" / "skills" / "book-to-skill",
    }
    extractor = roots[layout] / "scripts" / "extract.py"
    _touch(extractor)

    # Every layout is exercised from a NESTED directory on purpose. The probe
    # must find project-local roots no matter how deep the agent's CWD is —
    # that is the whole point of walking up to the project root. Running these
    # from the project root would hide a real discovery failure.
    raw = _run_probe(nested, _env(tmp_path, home))
    assert _resolve(nested, raw) == extractor.resolve()


@pytest.mark.parametrize("project_skill_dir", [".opencode", ".agents", ".claude"])
def test_opencode_project_probe_resolves_project_root_from_nested_cwd(
    tmp_path, project_skill_dir
):
    """Project-local roots must resolve from a deeply nested CWD.

    Regression guard: the probe used to list project roots as bare CWD-relative
    paths (`.opencode/skills/...`), so it only worked when the agent happened to
    sit at the project root. OpenCode itself walks up to the git worktree, so
    the spec has to do the same.
    """
    home = tmp_path / "home"
    project = _git_project(tmp_path)
    nested = project / "src" / "nested" / "deeper"
    nested.mkdir(parents=True)

    project_local = (
        project / project_skill_dir / "skills" / "book-to-skill" / "scripts" / "extract.py"
    )
    _touch(project_local)

    raw = _run_probe(nested, _env(tmp_path, home))
    assert _resolve(nested, raw) == project_local.resolve()


@pytest.mark.parametrize("project_skill_dir", [".opencode", ".agents", ".claude"])
def test_opencode_project_extractor_is_discoverable(tmp_path, project_skill_dir):
    home = tmp_path / "home"
    project = _git_project(tmp_path)

    project_local = (
        project / project_skill_dir / "skills" / "book-to-skill" / "scripts" / "extract.py"
    )
    _touch(project_local)

    raw = _run_probe(project, _env(tmp_path, home))
    assert _resolve(project, raw) == project_local.resolve()


def test_opencode_personal_root_is_reachable_beside_compatibility_roots(tmp_path):
    """The OpenCode root is probed even when a shared compatibility root exists.

    Probe order is spec-wide (not OpenCode-specific): `~/.claude/skills` is
    checked before `~/.config/opencode/skills`. This locks in only that the
    OpenCode root wins once the earlier compatibility roots are absent, so the
    host can be installed into its own directory without surprises.
    """
    home = tmp_path / "home"
    project = _git_project(tmp_path)

    native = home / ".config" / "opencode" / "skills" / "book-to-skill" / "scripts" / "extract.py"
    compat = home / ".claude" / "skills" / "book-to-skill" / "scripts" / "extract.py"
    _touch(native)
    _touch(compat)

    _run_probe(project, _env(tmp_path, home))  # spec order: compatibility first

    compat.unlink()
    selected = _resolve(project, _run_probe(project, _env(tmp_path, home)))
    assert selected == native.resolve()


def test_opencode_does_not_execute_hermes_only_project_layout(tmp_path):
    """A Hermes-only project layout is not an OpenCode discovery root.

    `~/.hermes` is deliberately left empty here: the spec probes the resolved
    Hermes home unconditionally, so a Hermes install under HOME would be picked
    up regardless of host. This asserts the project-local half — `.hermes/` is
    only reachable through the Hermes trust gate, never for OpenCode.
    """
    home = tmp_path / "home"
    home.mkdir(parents=True)
    project = _git_project(tmp_path)

    _touch(project / ".hermes" / "skills" / "book-to-skill" / "scripts" / "extract.py")

    assert _run_probe(project, _env(tmp_path, home)) == ""


def test_opencode_ignores_foreign_project_roots(tmp_path):
    """`.hermes/` is Hermes-only; OpenCode must not select it."""
    home = tmp_path / "home"
    home.mkdir(parents=True)
    project = _git_project(tmp_path)

    _touch(project / ".hermes" / "skills" / "book-to-skill" / "scripts" / "extract.py")
    _touch(project / ".github" / "skills" / "book-to-skill" / "scripts" / "extract.py")

    # `.github/skills` is shared and legitimately discoverable, so assert the
    # Hermes root specifically is not what gets selected.
    selected = _resolve(project, _run_probe(project, _env(tmp_path, home)))
    assert ".hermes" not in selected.parts


def test_opencode_destination_and_project_roots_are_documented():
    assert "**OpenCode**" in SKILL
    assert "~/.config/opencode/skills" in SKILL
    assert ".opencode/skills" in SKILL


def test_opencode_is_in_unknown_host_prompt_and_reload_guidance():
    assert "OpenCode, Hermes Agent, GitHub Copilot CLI, Amp, Codex, or Claude Code" in SKILL
    assert "OpenCode:             start a new session" in SKILL
