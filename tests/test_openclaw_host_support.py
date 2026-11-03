"""OpenClaw host-discovery contract in the converter spec."""

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


def _probe_env(home, state_dir=None):
    env = os.environ.copy()
    home_text = home.resolve().as_posix()
    if os.name == "nt":
        home_text = "/" + home_text[0].lower() + home_text[2:]
    env.update({"HOME": home_text})
    if state_dir is None:
        env.pop("OPENCLAW_STATE_DIR", None)
    else:
        state_text = state_dir.resolve().as_posix()
        if os.name == "nt":
            state_text = "/" + state_text[0].lower() + state_text[2:]
        env["OPENCLAW_STATE_DIR"] = state_text
    env.pop("HERMES_AGENT", None)
    env.pop("HERMES_HOME", None)
    return env


def _host_path(path_text):
    path_text = path_text.strip()
    if (
        os.name == "nt"
        and len(path_text) >= 3
        and path_text[0] == "/"
        and path_text[2] == "/"
    ):
        path_text = path_text[1].upper() + ":" + path_text[2:]
    return Path(path_text)


@pytest.mark.parametrize(
    "layout",
    [
        "personal-flat",
        "personal-grouped",
        "personal-deep",
        "personal-custom-state",
        "workspace-flat",
        "workspace-grouped",
        "workspace-deep",
    ],
)
@pytest.mark.skipif(
    os.name == "nt",
    reason="the probe uses POSIX Bash path semantics; the same cases run in Ubuntu CI",
)
def test_openclaw_extractor_probe_discovers_supported_layouts(tmp_path, layout):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    nested = project / "src" / "nested"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    roots = {
        "personal-flat": home / ".openclaw" / "skills" / "book-to-skill",
        "personal-grouped": home / ".openclaw" / "skills" / "group" / "subgroup" / "book-to-skill",
        "personal-deep": home / ".openclaw" / "skills" / "one" / "two" / "three" / "four" / "five" / "six" / "book-to-skill",
        "personal-custom-state": tmp_path / "custom-openclaw-state" / "skills" / "book-to-skill",
        "workspace-flat": project / "skills" / "book-to-skill",
        "workspace-grouped": project / "skills" / "group" / "subgroup" / "book-to-skill",
        "workspace-deep": project / "skills" / "one" / "two" / "three" / "four" / "five" / "six" / "book-to-skill",
    }
    extractor = roots[layout] / "scripts" / "extract.py"
    extractor.parent.mkdir(parents=True)
    extractor.touch()

    state_dir = roots[layout].parents[1] if layout == "personal-custom-state" else None
    result = subprocess.run(
        ["bash", "-c", _extract_probe_script()],
        cwd=nested,
        env=_probe_env(home, state_dir=state_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    selected = (nested / _host_path(result.stdout)).resolve()
    assert selected == extractor.resolve()


def test_openclaw_host_layouts_are_documented():
    assert "${OPENCLAW_STATE_DIR:-~/.openclaw}/skills" in SKILL
    assert "skills/book-to-skill/scripts/extract.py" in SKILL
    assert "openclaw skills list" in SKILL
    assert "OPENCLAW_STATE_DIR" in SKILL
    assert "~/.agents/skills` only with default state" in SKILL
