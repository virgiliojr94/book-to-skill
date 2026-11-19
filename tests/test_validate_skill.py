"""tools/validate_skill.py — frontmatter parsing is BOM-tolerant."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "validate_skill", Path(__file__).resolve().parent.parent / "tools" / "validate_skill.py"
)
validate_skill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validate_skill)

_SKILL = "---\nname: my-skill\ndescription: A test skill.\n---\n\n# Body\n"


def test_audit_accepts_skill_without_bom(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_bytes(_SKILL.encode("utf-8"))
    errors, _ = validate_skill.audit(str(p))
    assert errors == []


def test_audit_accepts_skill_with_utf8_bom(tmp_path):
    # A SKILL.md saved with a UTF-8 BOM used to fail with "no valid YAML
    # frontmatter" because the BOM broke text.startswith("---").
    p = tmp_path / "SKILL.md"
    p.write_bytes(b"\xef\xbb\xbf" + _SKILL.encode("utf-8"))
    errors, _ = validate_skill.audit(str(p))
    assert errors == []


def test_hermes_lens_accepts_standard_skill(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(_SKILL, encoding="utf-8")
    errors, _ = validate_skill.audit(str(p), lens="hermes")
    assert errors == []


def test_openclaw_lens_accepts_openclaw_metadata(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: openclaw-skill\n"
        "description: A test skill.\n"
        "homepage: https://example.com/skill\n"
        "user-invocable: true\n"
        "disable-model-invocation: false\n"
        "command-dispatch: tool\n"
        "command-tool: example\n"
        "command-arg-mode: raw\n"
        "metadata:\n"
        "  openclaw:\n"
        "    emoji: book\n"
        "---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p), lens="openclaw")
    assert errors == []
    assert not [warning for warning in warns if "frontmatter" in warning]


def test_openclaw_lens_rejects_underscore_identifiers(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: invalid_skill\ndescription: A test skill.\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p), lens="openclaw")
    assert any("name:" in error for error in errors)


def test_hermes_lens_recognizes_hermes_metadata(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: my-skill\n"
        "description: A test skill.\n"
        "version: 0.1.0\n"
        "author: Test Author\n"
        "license: MIT\n"
        "platforms: [linux, macos, windows]\n"
        "tags: [test]\n"
        "category: productivity\n"
        "required_environment_variables:\n"
        "  - name: TEST_TOKEN\n"
        "prerequisites:\n"
        "  commands: [python3]\n"
        "compatibility: Hermes Agent\n"
        "environments: [local]\n"
        "setup:\n"
        "  help: Configure the skill.\n"
        "required_credential_files: [~/.config/example]\n"
        "related_skills: [example]\n"
        "metadata:\n"
        "  hermes:\n"
        "    tags: [test]\n"
        "---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p), lens="hermes")
    assert errors == []
    assert not [warning for warning in warns if "frontmatter" in warning]


def test_hermes_lens_warns_when_trigger_exceeds_house_guideline(tmp_path):
    p = tmp_path / "SKILL.md"
    description = "A " + "long " * 14 + "description."
    p.write_text(
        f"---\nname: my-skill\ndescription: {description}\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p), lens="hermes")
    assert errors == []
    assert any("60 chars" in warning for warning in warns)


def test_hermes_lens_does_not_enforce_foreign_allowed_tools(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: my-skill\n"
        "description: A test skill.\n"
        "allowed-tools:\n"
        "  - Bash\n"
        "---\n\n```bash\npython3 scripts/example.py\n```\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p), lens="hermes")
    assert errors == []
    assert any("allowed-tools" in warning for warning in warns)


def test_hermes_lens_accepts_underscore_identifiers(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: valid_hermes_skill\ndescription: A test skill.\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p), lens="hermes")
    assert errors == []


def test_hermes_lens_accepts_dot_identifiers(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: valid.hermes.skill\ndescription: A test skill.\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p), lens="hermes")
    assert errors == []


def test_hermes_lens_rejects_unsupported_identifier_characters(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: _invalid\ndescription: A test skill.\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p), lens="hermes")
    assert any("name:" in error for error in errors)


def test_opencode_lens_accepts_standard_skill(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(_SKILL, encoding="utf-8")
    errors, _ = validate_skill.audit(str(p), lens="opencode")
    assert errors == []


def test_opencode_lens_recognizes_documented_frontmatter_keys(tmp_path):
    # OpenCode documents exactly five keys; anything else is ignored.
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: my-skill\n"
        "description: A test skill.\n"
        "license: MIT\n"
        "compatibility: opencode\n"
        "metadata:\n"
        "  audience: maintainers\n"
        "---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p), lens="opencode")
    assert errors == []
    assert not [warning for warning in warns if "frontmatter" in warning]


def test_opencode_lens_warns_on_keys_it_silently_ignores(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\n"
        "name: my-skill\n"
        "description: A test skill.\n"
        "allowed-tools:\n"
        "  - Bash\n"
        "---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p), lens="opencode")
    assert errors == []
    assert any("allowed-tools" in warning for warning in warns)


@pytest.mark.parametrize(
    "name",
    ["valid_skill", "valid.skill", "-leading", "trailing-", "double--hyphen", "Mixed"],
)
def test_opencode_lens_rejects_names_outside_official_pattern(tmp_path, name):
    p = tmp_path / "SKILL.md"
    p.write_text(
        f"---\nname: {name}\ndescription: A test skill.\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p), lens="opencode")
    assert any("name:" in error for error in errors)


def test_opencode_lens_accepts_single_hyphen_separators(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: git-release-2026\ndescription: A test skill.\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p), lens="opencode")
    assert errors == []


def test_opencode_lens_does_not_impose_description_soft_limit(tmp_path):
    # Hermes warns past 60 chars; OpenCode only enforces the 1024 hard cap.
    p = tmp_path / "SKILL.md"
    description = "A " + "long " * 20 + "description."
    p.write_text(
        f"---\nname: my-skill\ndescription: {description}\n---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p), lens="opencode")
    assert errors == []
    assert not [warning for warning in warns if "description:" in warning]


def _block_skill(indicator, body_lines):
    body = "\n".join("  " + ln for ln in body_lines)
    return f"---\nname: my-skill\ndescription: {indicator}\n{body}\nlicense: MIT\n---\n\n# Body\n"


@pytest.mark.parametrize("indicator", ["|", ">", "|-", ">-", "|+"])
def test_block_scalar_description_over_cap_is_rejected(tmp_path, indicator):
    # The value of `description: |` is the indented block, not the indicator:
    # reading only "|" made a 1,300-char description pass as 1 char long.
    p = tmp_path / "SKILL.md"
    p.write_text(_block_skill(indicator, ["word " * 20] * 13), encoding="utf-8")
    errors, _ = validate_skill.audit(str(p))
    assert any(e.startswith("description:") and "> 1024" in e for e in errors), errors


@pytest.mark.parametrize("indicator", ["|", ">"])
def test_block_scalar_description_under_cap_is_accepted(tmp_path, indicator):
    p = tmp_path / "SKILL.md"
    p.write_text(_block_skill(indicator, ["A short test skill", "on two lines."]), encoding="utf-8")
    errors, _ = validate_skill.audit(str(p))
    assert errors == []


def test_block_scalar_value_is_read_from_the_indented_lines():
    fm = "name: my-skill\ndescription: >\n  first line\n  second line\n\n  new paragraph\nlicense: MIT\n"
    assert validate_skill.get_scalar(fm, "description") == "first line second line\nnew paragraph"
    fm = "name: my-skill\ndescription: |\n  first line\n  second line\nlicense: MIT\n"
    assert validate_skill.get_scalar(fm, "description") == "first line\nsecond line"


def test_empty_block_scalar_description_is_missing(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: my-skill\ndescription: |\nlicense: MIT\n---\n\n# Body\n", encoding="utf-8")
    errors, _ = validate_skill.audit(str(p))
    assert "description: missing (required)" in errors


# --- YAML syntax of the frontmatter block -----------------------------------
# The regex parser in tools/validate_skill.py reads these files fine; host
# loaders (Claude Code, Pi, Copilot CLI) parse frontmatter as YAML, and a
# SKILL.md whose description is a *plain* scalar containing ': ' fails to load
# at all ("Nested mappings are not allowed in compact mappings"). Book titles
# are systematically "Title: Subtitle", so generated skills hit this often.

_TITLE_SKILL = (
    "---\n"
    "name: swett-professional-rails-testing\n"
    "description: Knowledge base from Professional Rails Testing: Tools and "
    "Principles (248-page PDF).\n"
    "---\n\n# Body\n"
)


def test_plain_description_containing_colon_space_is_an_error(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(_TITLE_SKILL, encoding="utf-8")
    errors, _ = validate_skill.audit(str(p))
    assert any("nested mapping" in e for e in errors), errors


def test_quoted_description_containing_colon_space_is_accepted(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        _TITLE_SKILL.replace("description: Knowledge", 'description: "Knowledge')
        .replace("(248-page PDF).", '(248-page PDF)."'),
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p))
    assert errors == [], errors


def test_quoted_description_with_escaped_inner_quotes_is_accepted(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: my-skill\n"
        'description: "Knowledge base from \\"DDIA\\" by Kleppmann."\n'
        "---\n\n# Body\n",
        encoding="utf-8",
    )
    errors, warns = validate_skill.audit(str(p))
    assert errors == [], errors
    assert not [w for w in warns if "frontmatter" in w], warns


def test_unterminated_quoted_description_is_an_error(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        '---\nname: my-skill\ndescription: "A test skill.\n---\n\n# Body\n',
        encoding="utf-8",
    )
    errors, _ = validate_skill.audit(str(p))
    assert any("not closed" in e for e in errors), errors


def test_plain_description_embedding_a_quote_warns(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        '---\nname: my-skill\ndescription: Working skill for "A Philosophy '
        'of Software Design".\n---\n\n# Body\n',
        encoding="utf-8",
    )
    _errors, warns = validate_skill.audit(str(p))
    assert any("embeds" in w for w in warns), warns


def test_hash_in_plain_description_warns(tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text(
        "---\nname: my-skill\ndescription: A test skill # not a comment\n"
        "---\n\n# Body\n",
        encoding="utf-8",
    )
    _errors, warns = validate_skill.audit(str(p))
    assert any("comment" in w for w in warns), warns


def test_yaml_safety_findings_ignores_block_scalars_and_nested_blocks():
    fm = (
        "name: my-skill\n"
        "description: >\n  Title: Subtitle, colon-safe.\n"
        "metadata:\n  openclaw:\n    emoji: book\n"
    )
    errors, warns = validate_skill.yaml_safety_findings(fm)
    assert errors == [], errors
    assert warns == [], warns


def test_strict_yaml_findings_reports_syntax_errors(tmp_path):
    findings = validate_skill.strict_yaml_findings(
        "name: my-skill\ndescription: A: B: C\n"
    )
    yaml = pytest.importorskip("yaml")  # PyYAML-optional path
    assert yaml is not None
    assert any("not valid YAML" in f for f in findings), findings
