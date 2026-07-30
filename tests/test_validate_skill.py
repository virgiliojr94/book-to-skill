import pytest

from tools.validate_skill import LENSES, audit


def write_skill(tmp_path, frontmatter, body="Use the skill.\n"):
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(
        f"---\n{frontmatter}---\n{body}",
        encoding="utf-8",
    )
    return skill_path


@pytest.mark.parametrize(
    ("lens", "allowed_tools"),
    [
        ("claude", "Bash Read"),
        ("copilot", "bash write"),
        ("amp", "Bash shell_command"),
    ],
)
def test_existing_lenses_still_accept_their_shell_tools(
    tmp_path, lens, allowed_tools
):
    skill_path = write_skill(
        tmp_path,
        f"name: example\ndescription: Example skill\nallowed-tools: {allowed_tools}\n",
        "```bash\npython3 scripts/example.py\n```\n",
    )

    assert audit(skill_path, lens=lens) == ([], [])


def test_codex_does_not_treat_allowed_tools_as_permissions(tmp_path):
    skill_path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "allowed-tools: Read\n"
        ),
        "```bash\npython3 scripts/example.py\n```\n",
    )

    errors, warns = audit(skill_path, lens="codex")

    assert errors == []
    assert len(warns) == 1
    assert "not enforced by OpenAI Codex 0.142.4" in warns[0]
    assert "omits" not in warns[0]


def test_claude_still_errors_when_declaration_omits_shell_tool(tmp_path):
    skill_path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "allowed-tools: Read\n"
        ),
        "```bash\npython3 scripts/example.py\n```\n",
    )

    errors, warns = audit(skill_path, lens="claude")

    assert len(errors) == 1
    assert "'Bash'" in errors[0]
    assert warns == []


@pytest.mark.parametrize(
    ("lens", "expects_error", "echoes_tool_name"),
    [
        ("claude", True, True),
        ("copilot", False, True),
        ("amp", False, True),
        ("codex", False, False),
    ],
)
def test_external_tool_lists_follow_lens_semantics(
    tmp_path, lens, expects_error, echoes_tool_name
):
    skill_path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "allowed-tools: linear__list_issues\n"
        ),
    )

    errors, warns = audit(skill_path, lens=lens)

    assert bool(errors) is expects_error
    assert len(warns) == 1
    assert ("linear__list_issues" in warns[0]) is echoes_tool_name


def test_codex_recognizes_portable_frontmatter(tmp_path):
    skill_path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "license: MIT\n"
            "metadata:\n"
            "  short-description: Short example\n"
        ),
    )

    assert audit(skill_path, lens="codex") == ([], [])


def test_codex_lens_is_available():
    assert LENSES["codex"]["label"] == "OpenAI Codex"
