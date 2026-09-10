"""OpenCode host-discovery contract in the converter spec.

OpenCode has no project-trust gate (unlike Hermes Agent): it discovers skills
automatically by walking up from the working directory to the git worktree, and
it reads `~/.config/opencode/skills`, `~/.agents/skills` and `~/.claude/skills`
as global roots. So these tests cover path discovery plus the guarantee that
OpenCode does not pick up another host's directory — not trust behavior.
"""

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")

def _bash_available():
    """True only when `bash -c` actually runs.

    Two traps on Windows make a bare `shutil.which("bash")` check wrong:

    * `C:\\Windows\\System32\\bash.exe` is a WSL stub that *exists* even when no
      Linux distribution is installed; invoking it exits 255 with a banner.
    * `CreateProcess` resolves a bare name against the system directory *before*
      PATH, so `subprocess.run(["bash", ...])` picks the stub even when a real
      bash appears first on PATH.

    Probe with the exact invocation the tests use so detection and execution
    agree.
    """
    try:
        probe = subprocess.run(
            ["bash", "-c", "true"],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


_BASH_AVAILABLE = _bash_available()

# The probe block in SKILL.md is a bash snippet; on hosts without a working bash
# (e.g. Windows without a WSL distro) the discovery contract cannot be exercised.
pytestmark = pytest.mark.skipif(
    not _BASH_AVAILABLE, reason="no working bash on PATH"
)


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
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _resolve(cwd, raw):
    selected = Path(raw)
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

    # Personal roots are probed as absolute `$HOME/...` paths, so they resolve
    # from any depth. Project-local roots other than Hermes' are probed
    # CWD-relative (`.opencode/skills/...`), matching `.github/`, `.claude/` and
    # `.agents/` — only the Hermes block rewrites them against $PROJECT_ROOT.
    # So the project layout is exercised from the project root, and the personal
    # layouts from a nested CWD to prove they do not depend on it.
    cwd = project if layout == "project-opencode" else nested
    raw = _run_probe(cwd, _env(tmp_path, home))
    assert _resolve(cwd, raw) == extractor.resolve()


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
