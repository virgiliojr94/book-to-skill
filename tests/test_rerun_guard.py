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

def _step0():
    return SKILL[SKILL.index("## Step 0"):SKILL.index("## Step 1 ")]


def test_reuse_requires_an_intact_matching_workdir():
    # Reviewer ask 1: reuse must be gated, not unconditional.
    guard = _step0()
    guard = guard[guard.index("Re-run guard"):]
    assert "only if it is still intact and still matches the current inputs and options" in guard
    assert "metadata.json" in guard
    assert "never restart extraction from scratch" not in guard


def test_reuse_match_covers_source_and_config():
    # Reviewer ask 1 said "matching the current source/config" — filenames alone
    # would let an in-place edit pass; the mode check covers the config half.
    guard = _step0()
    guard = guard[guard.index("Re-run guard"):]
    assert "same filenames **and sizes**" in guard
    assert "extraction_mode" in guard


def test_missing_or_stale_workdir_falls_back_to_fresh_extraction():
    # Reviewer ask 1: deleted/cleaned workdir or changed input -> fresh extraction.
    guard = _step0()
    guard = guard[guard.index("Re-run guard"):]
    assert "start a fresh extraction instead of resuming" in guard
    assert "missing (temp cleanup)" in guard
    assert "sources or their sizes no longer match" in guard
    assert "ask the user before discarding or resuming" in guard


def test_destination_resolved_before_the_step0_lookup():
    # Reviewer ask 2: resolution must precede the Mode 4 lookup, not follow it.
    step0 = _step0()
    assert "Resolve the destination root first" in step0
    assert step0.index("Resolve the destination root first") < step0.index(
        "flag this run as an **Update/Fold-in** operation"
    )


def test_step0_lookups_never_use_raw_skills_home():
    # Reviewer ask 2: SKILLS_HOME is only selected in Step 5, so Step 0 must not
    # consult it — a project-local request would hit the personal root by accident.
    assert "SKILLS_HOME" not in _step0()
