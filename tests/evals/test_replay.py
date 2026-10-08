"""Tests for deterministic fixture replay."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPLAY = ROOT / "tools" / "evals" / "replay.py"
FIXTURE = ROOT / "evals" / "fixtures" / "replay_trajectories.json"
SPEC = importlib.util.spec_from_file_location("eval_replay", REPLAY)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.path.insert(0, str(REPLAY.parent))
sys.modules[SPEC.name] = replay
SPEC.loader.exec_module(replay)


def test_fixture_has_exactly_five_synthetic_situations():
    fixture = replay.load_fixture(FIXTURE)
    assert fixture["schema_version"] == replay.SCHEMA_VERSION
    assert len(fixture["trajectories"]) == 5
    assert [item["question_id"] for item in fixture["trajectories"]] == [
        "01-correct", "02-wrong-routing", "03-wrong-answer", "04-irrelevant-opens", "05-unknown"]


def test_replay_returns_machine_readable_results():
    result = replay.replay(FIXTURE)
    assert result["schema_version"] == replay.RESULT_SCHEMA_VERSION
    assert result["aggregate"]["questions"] == 5
    assert len(result["questions"]) == 5


def test_cli_output_is_byte_identical_on_repeat():
    command = [sys.executable, str(REPLAY), str(FIXTURE)]
    first = subprocess.run(command, check=True, capture_output=True).stdout
    second = subprocess.run(command, check=True, capture_output=True).stdout
    assert first == second
    assert json.loads(first)["fixture_version"] == "1"


def test_cli_excludes_negative_usage_without_changing_classification(tmp_path):
    def trajectory(question_id, usage):
        return {
            "question_id": question_id,
            "expected": {"target": "book/chapter"},
            "observed": {
                "opens": ["book/chapter"], "answer_correct": True, "usage": usage,
            },
        }

    fixture = tmp_path / "negative_usage.json"
    fixture.write_text(json.dumps({
        "schema_version": replay.SCHEMA_VERSION,
        "fixture_version": "negative-usage",
        "trajectories": [
            trajectory("positive", {"input_tokens": 100, "output_tokens": 20, "calls": 2}),
            trajectory("negative", {"input_tokens": -100, "output_tokens": -20, "calls": -2}),
        ],
    }), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(REPLAY), str(fixture)],
        check=True, capture_output=True, text=True,
    )
    report = json.loads(completed.stdout)

    assert report["aggregate"]["recorded_usage"] == {
        "input_tokens": 100, "output_tokens": 20, "calls": 2,
    }
    assert report["aggregate"]["usage_observations"] == {
        "input_tokens": 1, "output_tokens": 1, "calls": 1,
    }
    assert [item["classification"] for item in report["questions"]] == ["correct", "correct"]
