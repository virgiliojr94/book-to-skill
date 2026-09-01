"""Hermes Agent host-discovery contract in the converter spec."""

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
GENERATION = (ROOT / "GENERATION.md").read_text(encoding="utf-8")


def _extract_probe_script():
    start = SKILL.index('SCRIPT_PATH=""')
    end = SKILL.index('\nif [ -z "$SCRIPT_PATH" ]', start)
    return SKILL[start:end] + '\nprintf "%s" "$SCRIPT_PATH"\n'


def _env_with_hermes_trust(tmp_path, home, hermes_home, trusted_dirs):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    hermes = bin_dir / "hermes"
    hermes.write_text(
        "#!/bin/sh\nprintf '%s\\n' " + repr(json.dumps([str(p) for p in trusted_dirs])) + "\n",
        encoding="utf-8",
    )
    hermes.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "HERMES_AGENT": "true",
            "HERMES_HOME": str(hermes_home),
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        }
    )
    return env


def test_hermes_is_named_as_supported_host():
    assert "Hermes Agent" in SKILL


@pytest.mark.parametrize(
    "layout",
    ["personal-flat", "personal-category", "project-flat", "project-category"],
)
def test_hermes_extractor_probe_discovers_supported_layouts(tmp_path, layout):
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes-profile"
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    nested = project / "src" / "nested"
    nested.mkdir(parents=True)

    roots = {
        "personal-flat": hermes_home / "skills" / "book-to-skill",
        "personal-category": hermes_home / "skills" / "productivity" / "book-to-skill",
        "project-flat": project / ".hermes" / "skills" / "book-to-skill",
        "project-category": project / ".hermes" / "skills" / "productivity" / "book-to-skill",
    }
    extractor = roots[layout] / "scripts" / "extract.py"
    extractor.parent.mkdir(parents=True)
    extractor.touch()

    env = _env_with_hermes_trust(
        tmp_path,
        home,
        hermes_home,
        [project] if layout.startswith("project-") else [],
    )
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=nested,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    selected = Path(result.stdout)
    if not selected.is_absolute():
        selected = nested / selected
    assert selected.resolve() == extractor.resolve()


@pytest.mark.parametrize("project_skill_dir", [".hermes", ".agents"])
def test_hermes_project_extractor_precedes_personal_installation(
    tmp_path, project_skill_dir
):
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes-profile"
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    nested = project / "src" / "nested"
    nested.mkdir(parents=True)

    personal = hermes_home / "skills" / "productivity" / "book-to-skill" / "scripts" / "extract.py"
    project_local = (
        project
        / project_skill_dir
        / "skills"
        / "productivity"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    for extractor in (personal, project_local):
        extractor.parent.mkdir(parents=True)
        extractor.touch()

    env = _env_with_hermes_trust(tmp_path, home, hermes_home, [project])
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=nested,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout).resolve() == project_local.resolve()


@pytest.mark.parametrize("project_skill_dir", [".hermes", ".agents"])
@pytest.mark.parametrize("cwd_relative", [".", "src/nested"])
def test_untrusted_hermes_project_cannot_override_personal_installation(
    tmp_path, project_skill_dir, cwd_relative
):
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes-profile"
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    nested = project / "src" / "nested"
    nested.mkdir(parents=True)
    run_from = project if cwd_relative == "." else nested

    personal = (
        hermes_home
        / "skills"
        / "productivity"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    untrusted = (
        project
        / project_skill_dir
        / "skills"
        / "productivity"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    for extractor in (personal, untrusted):
        extractor.parent.mkdir(parents=True)
        extractor.touch()

    env = _env_with_hermes_trust(tmp_path, home, hermes_home, [])
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=run_from,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout).resolve() == personal.resolve()


@pytest.mark.parametrize("project_skill_dir", [".agents", ".github", ".claude"])
def test_untrusted_project_candidate_is_not_executed(tmp_path, project_skill_dir):
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes-profile"
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    untrusted = (
        project
        / project_skill_dir
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    untrusted.parent.mkdir(parents=True)
    untrusted.touch()

    env = _env_with_hermes_trust(tmp_path, home, hermes_home, [])
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=project,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""


@pytest.mark.parametrize("project_skill_dir", [".github", ".claude"])
def test_hermes_ignores_foreign_project_roots_when_trusted(
    tmp_path, project_skill_dir
):
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes-profile"
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    foreign = (
        project
        / project_skill_dir
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    foreign.parent.mkdir(parents=True)
    foreign.touch()

    env = _env_with_hermes_trust(tmp_path, home, hermes_home, [project])
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=project,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""


def test_non_hermes_host_keeps_original_personal_precedence(tmp_path):
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes-profile"
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    personal = home / ".agents" / "skills" / "book-to-skill" / "scripts" / "extract.py"
    project_local = project / ".agents" / "skills" / "book-to-skill" / "scripts" / "extract.py"
    for extractor in (personal, project_local):
        extractor.parent.mkdir(parents=True)
        extractor.touch()

    env = _env_with_hermes_trust(tmp_path, home, hermes_home, [project])
    env.pop("HERMES_AGENT")
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=project,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout).resolve() == personal.resolve()


def test_hermes_project_candidates_require_enclosing_git_root(tmp_path):
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes-profile"
    project = tmp_path / "not-a-git-repository"
    project.mkdir()

    personal = (
        hermes_home
        / "skills"
        / "productivity"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    project_local = (
        project
        / ".hermes"
        / "skills"
        / "productivity"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    for extractor in (personal, project_local):
        extractor.parent.mkdir(parents=True)
        extractor.touch()

    env = _env_with_hermes_trust(tmp_path, home, hermes_home, [project])
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=project,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout).resolve() == personal.resolve()


def test_hermes_destination_and_project_roots_are_documented():
    assert "**Hermes Agent**" in SKILL
    assert "$HERMES_HOME/skills/<category>" in SKILL
    assert ".hermes/skills/<category>" in SKILL
    assert "hermes skills trust" in SKILL


def test_hermes_is_in_unknown_host_prompt_and_reload_guidance():
    assert "Hermes Agent, GitHub Copilot CLI, Amp, Codex, or Claude Code" in SKILL
    assert "Hermes Agent:         start a new session" in GENERATION
