"""Regression tests for the progressive-disclosure (NAV) split in SKILL.md.

Steps 4, 8, and 9 define an opt-in `NAV=progressive` mode where a generated
book skill keeps its SKILL.md lean (~1,800 tokens) and defers deep navigation
(topic index, source mapping, usage guide, scope) to a lazily-loaded
HOW_TO_USE.md. The default (`NAV=flat`) keeps everything in a single ~4,000
token SKILL.md.

These sections are LLM instructions, not executable code - nothing in this
project runs them. The tests pin the *prose* so a future edit that silently
removes the split, the "expand framework" trigger, or the distinct token
budgets fails loudly instead of drifting in review.
"""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = REPO_ROOT / "SKILL.md"


def _section(marker: str) -> str:
    """The SKILL.md section beginning at `marker`, up to the next `## Step ` heading."""
    if not SKILL_MD.is_file():
        pytest.skip("SKILL.md not present (e.g. installed sdist)")
    text = SKILL_MD.read_text(encoding="utf-8")
    start = text.find(marker)
    assert start != -1, f"SKILL.md no longer has a section beginning with {marker!r}"
    # Cut at the next top-level "## Step " heading, not any "## " - Steps 8/9
    # embed fenced markdown templates whose own "## " headings (e.g. "## How to
    # Use This Skill") would otherwise truncate the section early.
    end = text.find("\n## Step ", start + len(marker))
    return text[start:] if end == -1 else text[start:end]


def test_step_4_asks_navigation_tier_and_defaults_to_flat():
    """Step 4 must offer the navigation choice and default to flat.

    `NAV=flat` is the safe default - progressive is opt-in, so a model that
    skips the question still produces the plain single-file skill.
    """
    section = _section("## Step 4")
    assert "Ask about navigation tier" in section, (
        "Step 4 no longer asks the navigation-tier question"
    )
    assert "NAV=flat" in section, "Step 4 no longer names the flat default"
    assert "NAV=progressive" in section, "Step 4 no longer offers progressive mode"
    folded = section.casefold()
    assert "default to `flat`" in folded, (
        "Step 4 no longer states that flat is the default"
    )
    assert "default `nav=flat`" in folded, (
        "Step 4 no longer defaults NAV=flat when the step is skipped (Modes 2/3)"
    )


def test_step_8_generates_how_to_use_only_for_progressive():
    """Step 8 must emit HOW_TO_USE.md only under NAV=progressive, with its trigger."""
    section = _section("## Step 8")
    assert "HOW_TO_USE.md" in section, "Step 8 no longer generates HOW_TO_USE.md"
    assert "NAV=progressive" in section, (
        "Step 8 no longer gates HOW_TO_USE.md on NAV=progressive"
    )
    folded = section.casefold()
    assert "expand framework" in folded, (
        "Step 8 no longer names the 'expand framework' on-demand trigger"
    )
    assert "(if applicable)" in folded, (
        "Step 8 no longer marks source-mapping / depth-tier sections as conditional"
    )
    assert "under 2,000 tokens" in folded, (
        "Step 8 no longer caps the HOW_TO_USE.md deep-navigation layer"
    )


def test_step_9_branches_on_nav_with_distinct_token_budgets():
    """Step 9 must branch: flat stays under 4,000, progressive under 1,800 tokens."""
    section = _section("## Step 9")
    assert "NAV=flat" in section and "under 4,000 tokens" in section, (
        "Step 9 no longer keeps NAV=flat under the 4,000-token budget"
    )
    assert "NAV=progressive" in section and "under 1,800 tokens" in section, (
        "Step 9 no longer keeps NAV=progressive under the 1,800-token budget"
    )
    assert "If `NAV=flat`" in section, "Step 9 no longer has a NAV=flat template branch"
    assert "If `NAV=progressive`" in section, (
        "Step 9 no longer has a NAV=progressive template branch"
    )


def test_quality_rules_name_progressive_disclosure():
    """The quality rules must keep a progressive-disclosure rule (rule 9)."""
    section = _section("## Quality Rules")
    folded = section.casefold()
    assert "progressive disclosure" in folded, (
        "Quality Rules no longer name progressive disclosure"
    )
    assert "nav=progressive" in folded, (
        "Quality Rule 9 no longer ties progressive disclosure to NAV=progressive"
    )
    assert "expand framework" in folded, (
        "Quality Rule 9 no longer names the 'expand framework' trigger"
    )
