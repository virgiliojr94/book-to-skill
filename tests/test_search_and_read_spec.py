"""Regression and contract tests for Mode 2 (Search & Read) spec & progressive disclosure."""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = REPO_ROOT / "SKILL.md"
SEARCH_REF_MD = REPO_ROOT / "references" / "search-and-read.md"

_SPEC = importlib.util.spec_from_file_location(
    "validate_skill", REPO_ROOT / "tools" / "validate_skill.py"
)
validate_skill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validate_skill)


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def _modes_section(text: str) -> str:
    start = text.index("## Modes of Operation")
    end = text.index("## Skill Locations", start)
    return text[start:end]


def _step0_section(text: str) -> str:
    start = text.index("## Step 0")
    end = text.index("## Step 1 ", start)
    return text[start:end]


def test_local_modes_one_to_four_intact():
    """Existing local Modes 1-4 and their triggers must remain intact."""
    modes = _modes_section(_skill_text())
    for heading, trigger_fragment in [
        ("### 1. Full Conversion (Default)", "document/directory/glob paths"),
        ("### 2. Analyze Only", '"analyze", "just extract"'),
        ("### 3. Generate from Prior Analysis", "existing analysis notes"),
        ("### 4. Update / Fold-in (Existing Skill)", "update an existing skill"),
    ]:
        assert heading in modes, f"missing local mode heading: {heading}"
        assert trigger_fragment in modes, f"missing local trigger fragment: {trigger_fragment}"


def test_mode_2_search_and_read_trigger_and_lazy_pointer():
    """SKILL.md adds the Search & Read entry path and lazy pointer while staying lean."""
    text = _skill_text()
    lines = text.splitlines()
    assert len(lines) <= 910, f"SKILL.md grew too large ({len(lines)} lines)"

    assert "/book-to-skill search <query>" in text
    assert "references/search-and-read.md" in text
    assert "only when Mode 2 Search & Read is triggered" in text
    assert SEARCH_REF_MD.is_file(), "references/search-and-read.md is missing"

    # Progressive disclosure: detailed Mode 2 mechanics belong in references/search-and-read.md.
    for detail in ("get_details", "read(outline)", "read(cursor)", "remote_session.json"):
        assert detail not in text, f"detailed Mode 2 symbol {detail!r} leaked into root SKILL.md"


def test_step0_mcp_routing_and_mode1_fallback():
    """Step 0 routes search queries, detects MCP availability, and falls back to Mode 1."""
    step0 = _step0_section(_skill_text())
    lowered = step0.casefold()
    assert "libgen-mcp" in step0
    assert "mcp" in lowered
    assert "unavailable" in lowered
    assert "mode 1" in lowered
    assert "references/search-and-read.md" in step0
    assert "SKILLS_HOME" not in step0


def test_references_search_and_read_covers_workflow_and_warnings():
    """Lazy-loaded Mode 2 spec covers the full workflow, copyright gate, and failure warnings."""
    ref = SEARCH_REF_MD.read_text(encoding="utf-8")
    lowered = ref.casefold()

    # Discovery -> selection -> details -> confirmation -> reading -> synthesis -> scan -> publish
    for required in [
        "search",
        "get_details",
        "read(outline)",
        "read(section)",
        "read(cursor)",
        "sequential_fallback",
        "sanitize_extracted_text()",
        "full_text.txt",
        "glossary.md",
        "patterns.md",
        "cheatsheet.md",
        "scan_generated_skill.py",
        "Step 10",
        "Step 11",
        "--private",
    ]:
        assert required in ref, f"missing required workflow element in reference: {required}"

    # Explicit selection, copyright, cache, raw-fragment disposal, and truncation warnings
    assert "explicit selection" in lowered
    assert "discard raw fragments" in lowered
    assert "user confirmation does not equal copyright-holder authorization" in lowered
    assert "temporarily" in lowered and "cache" in lowered
    assert "model" in lowered and "transmit" in lowered
    assert "incomplete" in lowered and "truncated" in lowered
    assert "never call mcp `download`" in lowered


def test_step0_and_frontmatter_ux_clarity():
    """Frontmatter and Step 0 provide clear two-path onboarding and guided MCP install."""
    text = _skill_text()
    frontmatter, _ = validate_skill.parse_frontmatter(text)
    assert frontmatter is not None
    assert "/book-to-skill search <query>" in frontmatter
    step0 = _step0_section(text)
    assert 'avoid internal "Mode 1/Mode 2" labels' in step0
    assert "MCP available, query missing" in step0
    assert "MCP unavailable" in step0
    assert "install mcp" in step0
    assert "explicit confirmation" in step0

    ref = SEARCH_REF_MD.read_text(encoding="utf-8")
    assert "## Setup — Installing & Configuring an MCP Book Provider (Opt-in)" in ref
    assert "Never install packages or modify host MCP configuration files without explicit user consent." in ref
    assert "~/.gemini/config/mcp_config.json" in ref


@pytest.mark.parametrize("lens", sorted(validate_skill.LENSES.keys()))
def test_validate_skill_passes_all_six_lenses(lens):
    """SKILL.md must pass validate_skill.py on all 6 supported host lenses."""
    errors, _warns = validate_skill.audit(str(SKILL_MD), lens=lens)
    assert errors == [], f"validate_skill failed for lens {lens}: {errors}"
