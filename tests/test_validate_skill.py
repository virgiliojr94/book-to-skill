import pytest

from tools.validate_skill import LENSES, audit, split_tool_list


def write_skill(tmp_path, frontmatter, body="Use the skill.\n"):
    path = tmp_path / "SKILL.md"
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def test_split_tool_list_matches_grok_comma_and_parenthesis_rules():
    value = "Bash(git log --format=%h,%s), Grep read_file"

    assert split_tool_list(value) == [
        "Bash(git log --format=%h,%s)",
        "Grep",
        "read_file",
    ]


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
    path = write_skill(
        tmp_path,
        f"name: example\ndescription: Example skill\nallowed-tools: {allowed_tools}\n",
        "```bash\npython3 scripts/example.py\n```\n",
    )

    assert audit(path, lens=lens) == ([], [])


def test_grok_accepts_native_tools_aliases_and_documented_lowercase(tmp_path):
    path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "allowed-tools: run_terminal_command, Read, bash, grep\n"
        ),
        "```bash\npython3 scripts/example.py\n```\n",
    )

    assert audit(path, lens="grok") == ([], [])


def test_grok_recognizes_optional_frontmatter(tmp_path):
    path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "when-to-use: Use for examples\n"
            "when_to_use: Legacy spelling is also parsed\n"
            "argument-hint: <path>\n"
            "user-invocable: true\n"
            "disable-model-invocation: false\n"
            "model: grok-code-fast-1\n"
            "effort: high\n"
            "license: MIT\n"
            "compatibility: Requires Python\n"
            "paths: docs/**\n"
            "metadata:\n"
            "  author: Example\n"
        ),
    )

    assert audit(path, lens="grok") == ([], [])


def test_grok_warns_when_declaration_omits_shell_tool(tmp_path):
    path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "allowed-tools: read_file\n"
        ),
        "```bash\npython3 scripts/example.py\n```\n",
    )

    errors, warns = audit(path, lens="grok")

    assert errors == []
    assert len(warns) == 1
    assert "currently treats this field as declarative" in warns[0]


def test_claude_errors_when_declaration_omits_shell_tool(tmp_path):
    path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "allowed-tools: Read\n"
        ),
        "```bash\npython3 scripts/example.py\n```\n",
    )

    errors, warns = audit(path, lens="claude")

    assert len(errors) == 1
    assert "'Bash'" in errors[0]
    assert warns == []


@pytest.mark.parametrize(
    ("lens", "expects_error"),
    [
        ("claude", True),
        ("copilot", False),
        ("amp", False),
        ("grok", False),
    ],
)
def test_entirely_external_tool_lists_follow_lens_severity(
    tmp_path, lens, expects_error
):
    path = write_skill(
        tmp_path,
        (
            "name: example\n"
            "description: Example skill\n"
            "allowed-tools: linear__list_issues\n"
        ),
    )

    errors, warns = audit(path, lens=lens)

    assert bool(errors) is expects_error
    assert len(warns) == 1
    assert "linear__list_issues" in warns[0]


def test_grok_lens_is_available():
    assert LENSES["grok"]["label"] == "Grok Build"
