"""tools/validate_skill.py — frontmatter parsing is BOM-tolerant."""

import importlib.util
from pathlib import Path

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
