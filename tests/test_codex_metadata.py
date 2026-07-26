import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OPENAI_METADATA = ROOT / "agents" / "openai.yaml"


def metadata_scalar(key):
    text = OPENAI_METADATA.read_text(encoding="utf-8")
    match = re.search(rf"^\s+{re.escape(key)}:\s+\"([^\"]+)\"$", text, re.MULTILINE)
    assert match is not None, f"missing quoted interface.{key}"
    return match.group(1)


def documented_lookup():
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    block_start = skill_text.index('```bash\nHOST_AGENT="') + len("```bash\n")
    block_end = skill_text.index("\nPYTHON_BIN=", block_start)
    return skill_text[block_start:block_end]


def required_shell_tools():
    shell = shutil.which("sh")
    git = shutil.which("git")
    if shell is None or git is None:
        pytest.skip("a POSIX shell and git are required for the documented lookup")
    return shell, git


def test_codex_metadata_has_valid_interface_contract():
    text = OPENAI_METADATA.read_text(encoding="utf-8")
    short_description = metadata_scalar("short_description")
    default_prompt = metadata_scalar("default_prompt")

    assert metadata_scalar("display_name") == "Book to Skill"
    assert 25 <= len(short_description) <= 64
    assert "$book-to-skill" in default_prompt
    assert "\npolicy:" not in text
    assert "\ndependencies:" not in text
    assert "icon_" not in text


def test_documented_helper_lookup_finds_ancestor_agents_skill(tmp_path):
    shell, git = required_shell_tools()
    project = tmp_path / "project"
    nested_cwd = project / "packages" / "reader"
    helper = (
        project
        / ".agents"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    nested_cwd.mkdir(parents=True)
    helper.parent.mkdir(parents=True)
    helper.write_text("# helper fixture\n", encoding="utf-8")
    subprocess.run([git, "init", "-q", project], check=True)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "empty-home")
    env["HOST_AGENT"] = "codex"
    result = subprocess.run(
        [shell, "-c", f'{documented_lookup()}\nprintf "%s" "$SCRIPT_PATH"\n'],
        cwd=nested_cwd,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout) == helper


@pytest.mark.parametrize(
    ("host_agent", "personal_root"),
    [
        ("copilot", Path(".copilot/skills")),
        ("amp", Path(".agents/skills")),
        ("claude", Path(".claude/skills")),
    ],
)
def test_existing_hosts_keep_personal_helper_precedence(
    tmp_path, host_agent, personal_root
):
    shell, git = required_shell_tools()
    project = tmp_path / "project"
    nested_cwd = project / "packages" / "reader"
    project_helper = (
        nested_cwd
        / ".agents"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    personal_helper = (
        tmp_path
        / "home"
        / personal_root
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    nested_cwd.mkdir(parents=True)
    project_helper.parent.mkdir(parents=True)
    personal_helper.parent.mkdir(parents=True)
    project_helper.write_text("# project helper fixture\n", encoding="utf-8")
    personal_helper.write_text("# personal helper fixture\n", encoding="utf-8")
    subprocess.run([git, "init", "-q", project], check=True)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["HOST_AGENT"] = host_agent
    result = subprocess.run(
        [shell, "-c", f'{documented_lookup()}\nprintf "%s" "$SCRIPT_PATH"\n'],
        cwd=nested_cwd,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout) == personal_helper


def test_codex_project_helper_precedes_personal_install(tmp_path):
    shell, git = required_shell_tools()
    project = tmp_path / "project"
    nested_cwd = project / "packages" / "reader"
    project_helper = (
        project
        / ".agents"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    personal_helper = (
        tmp_path
        / "home"
        / ".agents"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    nested_cwd.mkdir(parents=True)
    project_helper.parent.mkdir(parents=True)
    personal_helper.parent.mkdir(parents=True)
    project_helper.write_text("# project helper fixture\n", encoding="utf-8")
    personal_helper.write_text("# personal helper fixture\n", encoding="utf-8")
    subprocess.run([git, "init", "-q", project], check=True)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["HOST_AGENT"] = "codex"
    result = subprocess.run(
        [shell, "-c", f'{documented_lookup()}\nprintf "%s" "$SCRIPT_PATH"\n'],
        cwd=nested_cwd,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout) == project_helper


def test_codex_personal_helper_precedes_other_host_roots(tmp_path):
    shell, git = required_shell_tools()
    project = tmp_path / "project"
    nested_cwd = project / "packages" / "reader"
    codex_helper = (
        tmp_path
        / "home"
        / ".agents"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    copilot_helper = (
        tmp_path
        / "home"
        / ".copilot"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    nested_cwd.mkdir(parents=True)
    codex_helper.parent.mkdir(parents=True)
    copilot_helper.parent.mkdir(parents=True)
    codex_helper.write_text("# Codex helper fixture\n", encoding="utf-8")
    copilot_helper.write_text("# Copilot helper fixture\n", encoding="utf-8")
    subprocess.run([git, "init", "-q", project], check=True)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["HOST_AGENT"] = "codex"
    result = subprocess.run(
        [shell, "-c", f'{documented_lookup()}\nprintf "%s" "$SCRIPT_PATH"\n'],
        cwd=nested_cwd,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout) == codex_helper


def test_documented_helper_lookup_stops_at_repository_root(tmp_path):
    shell, git = required_shell_tools()
    project = tmp_path / "parent" / "project"
    nested_cwd = project / "packages" / "reader"
    outside_helper = (
        tmp_path
        / "parent"
        / ".agents"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    nested_cwd.mkdir(parents=True)
    outside_helper.parent.mkdir(parents=True)
    outside_helper.write_text("# outside trust boundary\n", encoding="utf-8")
    subprocess.run([git, "init", "-q", project], check=True)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "empty-home")
    env["HOST_AGENT"] = "codex"
    result = subprocess.run(
        [shell, "-c", documented_lookup()],
        cwd=nested_cwd,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "Could not find scripts/extract.py" in result.stderr
    assert str(outside_helper) not in result.stdout


def test_documented_helper_lookup_fails_closed_for_unusable_git_root(tmp_path):
    shell, _ = required_shell_tools()
    project = tmp_path / "parent" / "project"
    nested_cwd = project / "packages" / "reader"
    outside_helper = (
        tmp_path
        / "parent"
        / ".agents"
        / "skills"
        / "book-to-skill"
        / "scripts"
        / "extract.py"
    )
    fake_bin = tmp_path / "fake-bin"
    fake_git = fake_bin / "git"
    nested_cwd.mkdir(parents=True)
    outside_helper.parent.mkdir(parents=True)
    fake_bin.mkdir()
    outside_helper.write_text("# outside trust boundary\n", encoding="utf-8")
    fake_git.write_text(
        "#!/bin/sh\nprintf '%s\\n' '/path/that/does/not/exist'\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "empty-home")
    env["HOST_AGENT"] = "codex"
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    result = subprocess.run(
        [shell, "-c", documented_lookup()],
        cwd=nested_cwd,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 1
    assert "Could not find scripts/extract.py" in result.stderr
    assert str(outside_helper) not in result.stdout
