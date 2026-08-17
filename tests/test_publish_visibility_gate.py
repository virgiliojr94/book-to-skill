"""Regression tests for the Step 11 publish visibility gate in SKILL.md.

Step 11 creates a GitHub repository from book-derived content. Its safety
property is that `gh repo create` runs with `--private` unless the user gives a
bare-word `public` answer to a question asked solely about repository
visibility. A regression here is invisible in review and only surfaces as a
public repository that should not exist, so the rule is asserted two ways:

1. the prose in SKILL.md still states the rule the model is meant to follow;
2. a reference implementation of that rule rejects the inputs a naive
   substring check would wrongly accept.

Test 2 does not execute anything from SKILL.md - nothing in this project does.
It pins the intended semantics next to the prose, so that a future edit
loosening the wording fails test 1 while test 2 still shows what the wording
was supposed to mean.
"""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = REPO_ROOT / "SKILL.md"


def _step_11() -> str:
    """The Step 11 section of SKILL.md, up to the next top-level heading."""
    if not SKILL_MD.is_file():
        pytest.skip("SKILL.md not present (e.g. installed sdist)")
    text = SKILL_MD.read_text(encoding="utf-8")
    marker = "## Step 11"
    start = text.find(marker)
    assert start != -1, "SKILL.md no longer has a Step 11 section"
    end = text.find("\n## ", start + len(marker))
    return text[start:] if end == -1 else text[start:end]


def _is_public_answer(reply: str) -> bool:
    """The visibility gate as specified: the reply must *be* `public`.

    Normalization is deliberately minimal - surrounding whitespace, casing, and
    trailing punctuation only. Anything that leaves more than the single word
    is a sentence, and a sentence is not a visibility answer.
    """
    return reply.strip().strip(".!?,;:").strip().casefold() == "public"


def test_repo_create_command_defaults_to_private():
    """The literal command in SKILL.md must carry --private.

    The maintainer's requirement is that the *command default* be private, so a
    model misreading the surrounding prose still cannot create a public repo.
    """
    section = _step_11()
    create_lines = [ln for ln in section.splitlines() if "gh repo create" in ln]
    assert create_lines, "Step 11 no longer contains a `gh repo create` command"
    command = next((ln for ln in create_lines if ln.strip().startswith("gh repo create")), None)
    assert command is not None, "no runnable `gh repo create` line in Step 11"
    assert "--private" in command, f"`gh repo create` lost its --private default: {command!r}"
    assert "--public" not in command, f"`gh repo create` hardcodes --public: {command!r}"


def test_visibility_is_asked_as_its_own_closed_question():
    """Visibility must not be inferred from the publish offer or earlier turns."""
    section = _step_11().casefold()
    assert "separate closed question" in section, (
        "Step 11 no longer states that visibility is asked as its own closed question"
    )
    assert "reply with one word" in section, (
        "Step 11 no longer requires a one-word visibility answer"
    )


def test_gate_forbids_substring_matching_and_names_the_licence_trap():
    """`public` must be the whole answer, and a licence statement must not count.

    "public domain" is ordinary vocabulary in this project - Moby-Dick is a
    benchmark book and the copyright gate actively asks users about the
    source's licence - so a user answering that question could otherwise
    satisfy the visibility gate without ever choosing to publish publicly.
    """
    section = _step_11().casefold()
    assert "substring matching is forbidden" in section, (
        "Step 11 no longer forbids substring matching on the visibility answer"
    )
    assert "public domain" in section, (
        "Step 11 no longer names the 'public domain' licence sentence as a non-answer"
    )
    assert "not a visibility answer" in section, (
        "Step 11 no longer states that a licence sentence is not a visibility answer"
    )


@pytest.mark.parametrize(
    "reply",
    [
        "public",
        "Public",
        "  public  ",
        "public.",
        "PUBLIC!",
    ],
)
def test_bare_word_public_opens_the_gate(reply):
    assert _is_public_answer(reply) is True


@pytest.mark.parametrize(
    "reply",
    [
        # The Step 10 trigger word that enters Step 11 at all.
        "publish",
        "publish it",
        # Statements about the source's licence, not the repository.
        "it is public domain",
        "the book is in the public domain",
        "it's publicly available",
        "public domain",
        # Paraphrase, ambiguity, silence, and the safe answer.
        "make it public",
        "public is fine i guess",
        "",
        "   ",
        "yes",
        "private",
    ],
)
def test_everything_else_stays_private(reply):
    assert _is_public_answer(reply) is False, (
        f"{reply!r} must not satisfy the visibility gate - it would create a public "
        "repository from book-derived content"
    )
