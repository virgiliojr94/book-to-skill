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
