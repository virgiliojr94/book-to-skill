"""Re-run guard contract in the converter spec (Step 0)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_step0_contains_rerun_guard():
    step0 = SKILL[SKILL.index("## Step 0"):SKILL.index("## Step 1 ")]
    assert "Re-run guard" in step0
    assert "STOP" in step0
    assert "Update/Fold-in (Mode 4)" in step0  # points the user at the escape hatch


def test_guard_covers_both_step5_naming_forms():
    # Step 5 can name a generated skill either by author-concept or by title.
    # The guard must check both, or an existing author-concept skill
    # (e.g. chilukuri-agenticops) is missed when the title differs.
    step0 = SKILL[SKILL.index("## Step 0"):SKILL.index("## Step 1 ")]
    assert "author-concept" in step0
    assert "by-title" in step0


def test_guard_runs_before_extraction():
    # The guard must live in Step 0, i.e. before the extraction step in file order.
    assert SKILL.index("Re-run guard") < SKILL.index("## Step 2 ")
