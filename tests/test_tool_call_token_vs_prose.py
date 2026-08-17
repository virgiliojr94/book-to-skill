"""`prompt.tool_call_tag` must catch the token, not the English phrase.

The rule exists to stop a generated skill from carrying a control token that
would make another agent act. It matched `\\btool[_ -]?call\\b` anywhere, so
every book explaining what a tool call is tripped the gate — and books about
agents and prompting are the most converted kind here.

The scan is a gate: it stops installation and asks for human review. A gate
that always fires on a whole category trains people to wave it through, which
costs more than the false positive it produces.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "tools"))

import scan_generated_skill as scanner

RULE = next(r for r in scanner._CONTENT_RULES if r[0] == "prompt.tool_call_tag")[1]


class TestControlTokensAreCaught:
    """One case per delimiter family that appears in real chat templates."""

    def test_angle_bracket_pair(self):
        assert RULE.search('<tool_call>{"name": "x"}</tool_call>')

    def test_special_token_pipes(self):
        assert RULE.search("<|tool_call|>")

    def test_square_brackets(self):
        assert RULE.search("[TOOL_CALL]")

    def test_square_bracket_closer(self):
        assert RULE.search("[/tool_call]")

    def test_template_placeholder(self):
        assert RULE.search("{{tool_call}}")

    def test_json_key(self):
        assert RULE.search('{"type": "tool_call", "id": 1}')

    def test_hyphen_and_case_variants(self):
        assert RULE.search("<TOOL-CALL>")
        assert RULE.search('{"tool-call": 1}')


class TestProseIsNotCaught:
    """The three lines below are verbatim from a real conversion that tripped
    the gate — a glossary and a cheatsheet explaining agent vocabulary."""

    def test_glossary_definition(self):
        assert not RULE.search(
            "Observation — Information returned to an agent after an action or tool call."
        )

    def test_chapter_line(self):
        assert not RULE.search(
            "Observation: data returned after an action or tool call."
        )

    def test_cheatsheet_cell(self):
        assert not RULE.search("It should know today's facts -> Retrieval/tool call")

    def test_ordinary_sentences(self):
        assert not RULE.search("the model emits a tool call and waits for the result")
        assert not RULE.search("tool_call latency dominates the loop")
        assert not RULE.search("a tool-call loop with three steps")
