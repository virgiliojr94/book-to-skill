"""Keep the entry-point host lists aligned with supported integrations."""

from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("path", "line_marker"),
    [
        ("README.md", "Turn any technical book"),
        ("README.md", "Works with any host"),
        ("docs/index.md", 'description: "Turn any book'),
        ("docs/index.md", '"description": "Converts books'),
        ("docs/index.md", "One `SKILL.md` runs"),
        ("docs/index.md", "**As an agent skill**"),
    ],
)
def test_entry_point_host_lists_include_codex(path, line_marker):
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    matching_lines = [line for line in lines if line_marker in line]

    assert len(matching_lines) == 1
    assert "Codex" in matching_lines[0]
