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
