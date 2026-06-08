"""Tests for tools/validate_index.py — index.json integrity checks."""

import importlib.util
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
spec = importlib.util.spec_from_file_location("validate_index", TOOLS_DIR / "validate_index.py")
vi = importlib.util.module_from_spec(spec)
sys.modules["validate_index"] = vi
spec.loader.exec_module(vi)


def _make_skill(tmp_path, index, with_files=("chapters/ch01-intro.md", "chapters/ch05-prfaq.md")):
    (tmp_path / "chapters").mkdir(exist_ok=True)
    for f in with_files:
        (tmp_path / f).write_text("# chapter", encoding="utf-8")
    (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


VALID_INDEX = {
    "skill": "working-backwards",
    "title": "Working Backwards",
    "chapters": [
        {"n": 1, "file": "chapters/ch01-intro.md", "title": "Intro", "frameworks": []},
        {"n": 5, "file": "chapters/ch05-prfaq.md", "title": "PR/FAQ", "frameworks": ["PR/FAQ"]},
    ],
    "topics": {"pr/faq": ["ch05"], "intro": ["ch01"]},
}


class TestValidateIndex:
    def test_valid_index_passes(self, tmp_path):
        sd = _make_skill(tmp_path, VALID_INDEX)
        errors, warnings = vi.validate(sd)
        assert errors == []

    def test_missing_index_errors(self, tmp_path):
        errors, _ = vi.validate(tmp_path)
        assert any("not found" in e for e in errors)

    def test_chapter_file_missing_on_disk(self, tmp_path):
        sd = _make_skill(tmp_path, VALID_INDEX, with_files=("chapters/ch01-intro.md",))
        errors, _ = vi.validate(sd)
        assert any("does not exist on disk" in e for e in errors)

    def test_topic_points_to_unknown_chapter(self, tmp_path):
        idx = json.loads(json.dumps(VALID_INDEX))
        idx["topics"]["ghost"] = ["ch99"]
        sd = _make_skill(tmp_path, idx)
        errors, _ = vi.validate(sd)
        assert any("unknown chapter 'ch99'" in e for e in errors)

    def test_uppercase_topic_key_errors(self, tmp_path):
        idx = json.loads(json.dumps(VALID_INDEX))
        idx["topics"]["PR_FAQ"] = ["ch05"]
        sd = _make_skill(tmp_path, idx)
        errors, _ = vi.validate(sd)
        assert any("not lowercase" in e for e in errors)

    def test_unreachable_chapter_warns(self, tmp_path):
        idx = json.loads(json.dumps(VALID_INDEX))
        del idx["topics"]["intro"]  # ch01 now unreachable
        sd = _make_skill(tmp_path, idx)
        errors, warnings = vi.validate(sd)
        assert errors == []
        assert any("not reachable" in w for w in warnings)

    def test_invalid_json_errors(self, tmp_path):
        (tmp_path / "index.json").write_text("{not json", encoding="utf-8")
        errors, _ = vi.validate(tmp_path)
        assert any("not valid JSON" in e for e in errors)
