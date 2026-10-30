"""The generated SKILL.md template points the agent at the extracted full text,
so the skill works as an index into the real book."""
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


def test_template_points_to_full_text():
    body = SKILL.read_text(encoding="utf-8")
    template = body.split("## Step 9 — Generate the master SKILL.md", 1)[1].split("## Step 9.5", 1)[0]
    assert "<output_text from metadata.json>" in template
    assert "grep" in template
