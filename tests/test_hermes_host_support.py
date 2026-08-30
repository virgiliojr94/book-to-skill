"""Hermes Agent host-discovery contract in the converter spec."""

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")


def _extract_probe_script():
    start = SKILL.index('SCRIPT_PATH=""')
    end = SKILL.index('\nif [ -z "$SCRIPT_PATH" ]', start)
    return SKILL[start:end] + '\nprintf "%s" "$SCRIPT_PATH"\n'


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

    roots = {
        "personal-flat": hermes_home / "skills" / "book-to-skill",
        "personal-category": hermes_home / "skills" / "productivity" / "book-to-skill",
        "project-flat": project / ".hermes" / "skills" / "book-to-skill",
        "project-category": project / ".hermes" / "skills" / "productivity" / "book-to-skill",
    }
    extractor = roots[layout] / "scripts" / "extract.py"
    extractor.parent.mkdir(parents=True)
    extractor.touch()

    env = os.environ.copy()
    env.update({"HOME": str(home), "HERMES_HOME": str(hermes_home)})
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=project,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    selected = Path(result.stdout)
    if not selected.is_absolute():
        selected = project / selected
    assert selected.resolve() == extractor.resolve()


def test_hermes_destination_and_project_roots_are_documented():
    assert "**Hermes Agent**" in SKILL
    assert "$HERMES_HOME/skills/<category>" in SKILL
    assert ".hermes/skills/<category>" in SKILL
    assert "hermes skills trust" in SKILL


def test_hermes_is_in_unknown_host_prompt_and_reload_guidance():
    assert "Hermes Agent, GitHub Copilot CLI, Amp, Codex, or Claude Code" in SKILL
    assert "Hermes Agent:         start a new session" in SKILL
