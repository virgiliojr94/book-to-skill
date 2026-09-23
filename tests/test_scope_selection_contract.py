"""Scope-selection contract documented by the book-to-skill skill."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
INSTALL = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")


def _opencode_table_row() -> str:
    """The single markdown table row describing the OpenCode host."""
    rows = [
        line
        for line in SKILL.splitlines()
        if line.lstrip().startswith("|") and "**OpenCode**" in line
    ]
    assert len(rows) == 1, f"expected exactly one OpenCode host row, got {rows!r}"
    return rows[0]


def _selection_rules() -> list[str]:
    """Every numbered line in the `Selection rules:` block, in document order.

    The block ends at the first non-blank line that is not numbered (the
    `Set SKILLS_HOME ...` paragraph), so a second list restarting at `1.`
    is still collected and makes the sequence assertion fail.
    """
    assert SKILL.count("Selection rules:") == 1, "expected exactly one `Selection rules:` block"
    tail = SKILL.split("Selection rules:", 1)[1].splitlines()
    rules: list[str] = []
    for raw in tail:
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^\d+\.\s", line):
            rules.append(line)
            continue
        break
    return rules


def test_scope_defaults_to_personal_without_a_mandatory_prompt():
    assert "preserve the established personal default" in SKILL
    assert "Do not ask a mandatory scope question" in SKILL
    assert "does not ask a mandatory scope question" in INSTALL


def test_explicit_project_scope_is_documented_as_opt_in():
    assert "BOOK_TO_SKILL_SCOPE=project" in SKILL
    assert "BOOK_TO_SKILL_SCOPE=project" in INSTALL
    assert "project-local/project output selects the project-local row" in SKILL
    assert "After:  BOOK_TO_SKILL_SCOPE=project" in INSTALL


def test_personal_destination_does_not_claim_approval_free_writes():
    assert "may still require host approval before writing" in SKILL
    assert "may require host approval to write inside the project" in INSTALL
    assert "no extra approval" not in SKILL


def test_skill_has_no_merge_residue():
    """A bad conflict resolution must not ship a literal HEAD line or a marker."""
    residue = [n for n, line in enumerate(SKILL.splitlines(), 1) if line.strip() == "HEAD"]
    assert not residue, f"literal `HEAD` merge residue on line(s) {residue}"
    for marker in ("<<<<<<<", "=======", ">>>>>>>"):
        assert marker not in SKILL, f"conflict marker {marker!r} left in SKILL.md"


def test_skill_has_exactly_one_selection_rule_list():
    """#125 replaced the ask-on-fresh-install policy; its residue must not return.

    The list must be ONE contiguous block (no duplicate or orphan rules) and the
    host-identification prompt in the final rule must name every host the spec
    supports. The rule count itself is expected to grow as hosts are added
    (OpenClaw added rules 7-8); asserting a frozen count made this test fail on
    every host addition (review request, 2026-09-22).
    """
    assert "fresh machine" not in SKILL, "pre-#125 `fresh machine` policy text reappeared"
    assert "ask the user which root to create" not in SKILL, (
        "pre-#125 `ask the user which root to create` policy text reappeared"
    )
    rules = _selection_rules()
    numbers = [int(re.match(r"^(\d+)\.", rule).group(1)) for rule in rules]
    assert numbers and numbers == list(range(1, len(numbers) + 1)), (
        f"`Selection rules:` must be ONE contiguous 1..N list with no gaps or "
        f"duplicates, got {numbers}"
    )
    prompt_rules = [r for r in rules if "Which agent are you running" in r]
    assert len(prompt_rules) == 1, (
        f"exactly one rule must ask the user which host they are running, "
        f"got {len(prompt_rules)}: {[r[:60] for r in prompt_rules]}"
    )
    for host in ("Copilot CLI", "Amp", "Codex", "Claude Code"):
        assert host in prompt_rules[0], f"host prompt must name {host}"


def test_personal_default_stays_cross_agent_after_opencode_support():
    assert 'preserve the established personal default' in SKILL
    assert "~/.agents/skills" in SKILL
    rules = _selection_rules()
    assert "`SKILLS_HOME` to `~/.agents/skills`" in rules[0], (
        "rule 1 must set SKILLS_HOME to the cross-agent root"
    )


def test_opencode_row_prefers_the_cross_agent_default():
    """#125 keeps ~/.agents/skills as the personal root; OpenCode is no exception."""
    row = _opencode_table_row()
    assert "~/.agents/skills" in row, "OpenCode row must keep the cross-agent personal root"
    assert row.index("~/.agents/skills") < row.index("~/.config/opencode/skills"), (
        "OpenCode row must present ~/.agents/skills before the private root"
    )


def test_opencode_prose_has_no_private_root_preference():
    assert "prefer the OpenCode-managed" not in SKILL, (
        "the private-root preference contradicts the #125 default"
    )
    assert "use the OpenCode-managed root only when the user asks for it" in SKILL, (
        "OpenCode prose must say the private root is opt-in"
    )


def test_opencode_cache_root_is_not_an_authoring_destination():
    assert "~/.cache/opencode/skills" not in _opencode_table_row(), (
        "the download cache must never appear as a host skill root"
    )
    if "~/.cache/opencode/skills" in SKILL:
        assert "not an authoring root" in SKILL, (
            "when mentioned, the cache must be labelled as a cache, not a destination"
        )
