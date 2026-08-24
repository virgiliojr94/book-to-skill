#!/usr/bin/env python3
"""Pure scoring and accounting for synthetic evaluation trajectories."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

UNKNOWN = "unknown"


def _state(value: Any) -> Any:
    """Keep only explicit boolean observations; absence remains unknown."""
    return value if isinstance(value, bool) else UNKNOWN


def score_trajectory(trajectory: Dict[str, Any]) -> Dict[str, Any]:
    """Score one trajectory without loading files or deriving missing observations."""
    expected = trajectory.get("expected", {})
    observed = trajectory.get("observed", {})
    target = expected.get("target")
    opens = observed.get("opens")
    opened_target = (
        any(opened == target for opened in opens)
        if isinstance(opens, list) and target is not None
        else UNKNOWN
    )
    answer_correct = _state(observed.get("answer_correct"))
    route_correct = _state(observed.get("route_correct"))
    evidence_reached = _state(observed.get("evidence_reached"))
    if "route_correct" not in observed and opened_target is not UNKNOWN:
        route_correct = opened_target
    if "evidence_reached" not in observed and opened_target is not UNKNOWN:
        evidence_reached = opened_target

    if UNKNOWN in (route_correct, evidence_reached, answer_correct):
        classification = UNKNOWN
    elif not route_correct:
        classification = "wrong_routing"
    elif not answer_correct:
        classification = "wrong_answer"
    elif isinstance(opens, list) and target is not None and opens.index(target) > 0:
        classification = "irrelevant_opens_before_target"
    else:
        classification = "correct"

    usage = observed.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return {
        "question_id": trajectory["question_id"],
        "classification": classification,
        "routing_correct": route_correct,
        "evidence_reached": evidence_reached,
        "answer_correct": answer_correct,
        "usage": {key: usage.get(key) if isinstance(usage.get(key), int) else UNKNOWN
                  for key in ("input_tokens", "output_tokens", "calls")},
    }


def aggregate(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate recorded usage and classifications; never estimate missing usage."""
    items = list(results)
    counts: Dict[str, int] = {}
    totals = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    recorded = {key: 0 for key in totals}
    for result in items:
        label = result["classification"]
        counts[label] = counts.get(label, 0) + 1
        for key in totals:
            value = result["usage"][key]
            if value != UNKNOWN:
                totals[key] += value
                recorded[key] += 1
    return {
        "questions": len(items),
        "classifications": counts,
        "recorded_usage": totals,
        "usage_observations": recorded,
    }


def score(trajectories: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Return deterministic per-question and aggregate replay results."""
    questions: List[Dict[str, Any]] = [score_trajectory(item) for item in trajectories]
    questions.sort(key=lambda item: item["question_id"])
    return {"questions": questions, "aggregate": aggregate(questions)}
