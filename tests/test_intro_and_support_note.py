"""Two quiet messages: attribution at the start, funding at the end.

The ask sits at the end on purpose — the reader has just received something
that worked — and only when the run succeeded. Asking someone to fund a tool
that just failed on their document is the fastest way to make the line
invisible.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill import utils


class TestIntro:
    def test_names_the_project_and_the_licence(self, capsys):
        utils.print_intro()

        err = capsys.readouterr().err
        assert "book-to-skill" in err
        assert "MIT-licensed" in err

    def test_does_not_ask_for_money(self, capsys):
        """The start of a run has delivered nothing yet."""
        utils.print_intro()

        err = capsys.readouterr().err
        assert "sponsors" not in err.lower()


class TestSupportNote:
    def test_points_at_the_sponsors_page(self, capsys):
        utils.print_support_note()

        out = capsys.readouterr().out
        assert "github.com/sponsors/virgiliojr94" in out

    def test_goes_to_stdout_with_the_rest_of_the_report(self, capsys):
        """stderr is unbuffered and stdout is not when piped — mixing the two
        puts the closing line at the top of the run."""
        utils.print_support_note()

        captured = capsys.readouterr()
        assert captured.out.strip()
        assert captured.err == ""

    def test_stays_short(self, capsys):
        """Two lines. A wall of text here reads as a donation banner."""
        utils.print_support_note()

        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
        assert len(lines) <= 2
