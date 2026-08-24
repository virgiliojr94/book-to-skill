"""Focused tests for offline trajectory scoring."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("eval_score", ROOT / "tools" / "evals" / "score.py")
score = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = score
SPEC.loader.exec_module(score)


def trajectory(question_id, opens, answer_correct=True, usage=None):
    return {"question_id": question_id, "expected": {"target": "book/chapter"},
            "observed": {"opens": opens, "answer_correct": answer_correct,
                         "usage": usage or {}}}


def test_classifies_correct_routing_and_answer():
    assert score.score_trajectory(trajectory("q", ["book/chapter"]))["classification"] == "correct"


def test_classifies_wrong_routing():
    assert score.score_trajectory(trajectory("q", ["other/chapter"], False))["classification"] == "wrong_routing"


def test_classifies_target_evidence_with_wrong_answer():
    result = score.score_trajectory(trajectory("q", ["book/chapter"], False))
    assert result["classification"] == "wrong_answer"
    assert result["evidence_reached"] is True


def test_classifies_irrelevant_opens_before_target():
    assert score.score_trajectory(trajectory("q", ["other/one", "other/two", "book/chapter"]))["classification"] == "irrelevant_opens_before_target"


def test_unknown_observability_is_never_inferred():
    result = score.score_trajectory({"question_id": "q", "expected": {"target": "book/chapter"}, "observed": {}})
    assert result["classification"] == score.UNKNOWN
    assert result["routing_correct"] == score.UNKNOWN
    assert result["evidence_reached"] == score.UNKNOWN
    assert result["answer_correct"] == score.UNKNOWN


def test_explicit_unknown_remains_unknown_despite_observed_open():
    item = trajectory("q", ["book/chapter"])
    item["observed"]["route_correct"] = "unknown"
    result = score.score_trajectory(item)
    assert result["routing_correct"] == score.UNKNOWN
    assert result["classification"] == score.UNKNOWN


def test_aggregate_sums_only_recorded_tokens_and_calls():
    result = score.score([trajectory("b", ["book/chapter"], usage={"input_tokens": 4, "calls": 2}),
                          trajectory("a", [], usage={"output_tokens": 3})])
    assert [item["question_id"] for item in result["questions"]] == ["a", "b"]
    assert result["aggregate"]["recorded_usage"] == {"input_tokens": 4, "output_tokens": 3, "calls": 2}
    assert result["aggregate"]["usage_observations"] == {"input_tokens": 1, "output_tokens": 1, "calls": 1}
