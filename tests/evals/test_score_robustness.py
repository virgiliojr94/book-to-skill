"""Scoring must consume whatever a harness recorded, without crashing or inventing.

`tools/evals/score.py` documents itself as scoring "without loading files or
deriving missing observations", and `aggregate` promises to "never estimate
missing usage". Two things broke that contract.

1. `opens.index(target)` was called unguarded. It is only reached when
   `route_correct` and `answer_correct` are both true — but `route_correct` is
   only *derived* from `opens` when the harness did not record it. A harness that
   records `route_correct` itself, while `opens` does not contain the target
   verbatim, raised `ValueError` and killed the entire scoring run rather than
   one question.

2. `isinstance(value, int)` accepted `True`, because `bool` subclasses `int` in
   Python. A JSON `true` in a usage field was therefore treated as a recorded
   count and summed as 1 — precisely the estimate the module promises not to make.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "tools"))

from evals.score import UNKNOWN, aggregate, score, score_trajectory

RECORDED = {"route_correct": True, "evidence_reached": True, "answer_correct": True}


def _trajectory(question_id, target, opens, **observed):
    return {
        "question_id": question_id,
        "expected": {"target": target},
        "observed": dict(observed, opens=opens),
    }


class TestTargetMissingFromOpens:
    """Recorded booleans must be trusted, not cross-checked into a crash."""

    @pytest.mark.parametrize(
        "opens, label",
        [
            (["chapters/ch01.md"], "a different file was opened"),
            ([], "nothing was opened"),
            (["./chapters/ch02.md"], "path normalisation differs"),
            (["chapters/CH02.MD"], "case differs"),
        ],
    )
    def test_does_not_crash(self, opens, label):
        result = score_trajectory(
            _trajectory("q", "chapters/ch02.md", opens, **RECORDED)
        )

        assert result["classification"] == "correct", label

    def test_recorded_flags_are_passed_through_unchanged(self):
        result = score_trajectory(
            _trajectory("q", "b.md", ["a.md"], **RECORDED)
        )

        assert result["routing_correct"] is True
        assert result["evidence_reached"] is True
        assert result["answer_correct"] is True

    def test_a_single_bad_row_does_not_kill_the_run(self):
        """One unscoreable question used to abort every other question."""
        trajectories = [
            _trajectory("q1", "a.md", ["a.md"], **RECORDED),
            _trajectory("q2", "b.md", ["a.md"], **RECORDED),
            _trajectory("q3", "c.md", ["c.md"], **RECORDED),
        ]

        report = score(trajectories)

        assert [item["question_id"] for item in report["questions"]] == ["q1", "q2", "q3"]
        assert report["aggregate"]["questions"] == 3


class TestDerivedRoutingUnchanged:
    """When the harness did NOT record routing, it is still derived from opens."""

    def test_target_absent_is_wrong_routing(self):
        result = score_trajectory(
            _trajectory("q", "a.md", ["b.md"], answer_correct=True)
        )

        assert result["classification"] == "wrong_routing"
        assert result["routing_correct"] is False

    def test_target_first_is_correct(self):
        result = score_trajectory(
            _trajectory("q", "a.md", ["a.md", "b.md"], answer_correct=True)
        )

        assert result["classification"] == "correct"

    def test_target_after_others_is_flagged(self):
        result = score_trajectory(
            _trajectory("q", "b.md", ["a.md", "b.md"], answer_correct=True)
        )

        assert result["classification"] == "irrelevant_opens_before_target"

    def test_duplicate_opens_use_the_first_position(self):
        result = score_trajectory(
            _trajectory("q", "b.md", ["b.md", "a.md", "b.md"], answer_correct=True)
        )

        assert result["classification"] == "correct"

    def test_missing_answer_is_unknown(self):
        result = score_trajectory(_trajectory("q", "a.md", ["a.md"]))

        assert result["classification"] == UNKNOWN

    def test_wrong_answer_still_reported(self):
        result = score_trajectory(
            _trajectory("q", "a.md", ["a.md"], answer_correct=False)
        )

        assert result["classification"] == "wrong_answer"


class TestUsageCountsRejectBooleans:
    """`bool` is an `int`; a recorded `true` is not a count."""

    @pytest.mark.parametrize("field", ["input_tokens", "output_tokens", "calls"])
    def test_true_is_not_a_count(self, field):
        usage = {"input_tokens": 5, "output_tokens": 1, "calls": 2}
        usage[field] = True

        result = score_trajectory(
            _trajectory("q", "a", ["a"], answer_correct=True, usage=usage)
        )

        assert result["usage"][field] == UNKNOWN

    def test_false_is_not_a_count(self):
        result = score_trajectory(
            _trajectory("q", "a", ["a"], answer_correct=True, usage={"calls": False})
        )

        assert result["usage"]["calls"] == UNKNOWN

    def test_booleans_are_not_summed_into_totals(self):
        results = [
            score_trajectory(
                _trajectory("q1", "a", ["a"], answer_correct=True,
                            usage={"calls": True, "input_tokens": 10,
                                   "output_tokens": 2})
            ),
            score_trajectory(
                _trajectory("q2", "a", ["a"], answer_correct=True,
                            usage={"calls": 3, "input_tokens": 20,
                                   "output_tokens": 4})
            ),
        ]

        summary = aggregate(results)

        # Only the genuine 3 is counted, and only one observation is recorded.
        assert summary["recorded_usage"]["calls"] == 3
        assert summary["usage_observations"]["calls"] == 1
        assert summary["recorded_usage"]["input_tokens"] == 30
        assert summary["usage_observations"]["input_tokens"] == 2

    def test_genuine_integers_still_recorded(self):
        result = score_trajectory(
            _trajectory("q", "a", ["a"], answer_correct=True,
                        usage={"input_tokens": 7, "output_tokens": 0, "calls": 1})
        )

        assert result["usage"] == {"input_tokens": 7, "output_tokens": 0, "calls": 1}

    def test_non_numeric_usage_is_unknown(self):
        result = score_trajectory(
            _trajectory("q", "a", ["a"], answer_correct=True,
                        usage={"calls": "3", "input_tokens": 1.5})
        )

        assert result["usage"]["calls"] == UNKNOWN
        assert result["usage"]["input_tokens"] == UNKNOWN
