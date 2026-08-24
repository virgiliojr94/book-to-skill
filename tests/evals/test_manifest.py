"""Tests for deterministic evaluation run manifests."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "evals" / "manifest.py"
SPEC = importlib.util.spec_from_file_location("eval_manifest", MODULE_PATH)
manifest = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = manifest
SPEC.loader.exec_module(manifest)


def config(source_name="source.txt"):
    return {
        "sources": [{"id": "fixture", "path": source_name}],
        "condition": "flat",
        "question_set_hash": "questions-sha256",
        "models": {"answer": "test-model", "generation": "unsupported"},
        "harness_id": "fixture-harness",
        "prompt_hashes": {"answer": "prompt-sha256"},
        "config_hashes": {"runner": "config-sha256"},
        "seed": "unsupported",
        "repetition": "unsupported",
        "budgets": {"max_calls": 1, "max_input_tokens": 100, "max_output_tokens": 20},
        "artifacts": ".eval-work/artifacts/run",
        "results": ".eval-work/results/run.json",
        "reason": "smallest discriminating run",
        "decision": "whether to continue",
    }


def test_identical_inputs_have_identical_manifest_and_run_id(tmp_path):
    (tmp_path / "source.txt").write_text("café", encoding="utf-8")
    first = manifest.build_manifest(config(), tmp_path)
    second = manifest.build_manifest(config(), tmp_path)

    assert first == second
    assert first["sources"] == [{"id": "fixture", "sha256": manifest.sha256_file(tmp_path / "source.txt")}]
    assert "café" == json.loads(manifest.canonical_json({"text": "café"}))["text"]


def test_material_config_or_source_change_alters_run_id(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_bytes("café".encode("utf-8"))
    monkeypatch.setattr(manifest, "_commit", lambda _: "a" * 40)
    original = manifest.build_manifest(config(), tmp_path)
    changed_condition = config()
    changed_condition["condition"] = "structured"
    assert manifest.build_manifest(changed_condition, tmp_path)["run_id"] != original["run_id"]

    source.write_bytes("caffè".encode("utf-8"))
    assert manifest.build_manifest(config(), tmp_path)["run_id"] != original["run_id"]

    monkeypatch.setattr(manifest, "_commit", lambda _: "b" * 40)
    assert manifest.build_manifest(config(), tmp_path)["run_id"] != original["run_id"]


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda value: value.pop("condition"), "missing required fields"),
        (lambda value: value["budgets"].update(max_calls=-1), "max_calls"),
        (lambda value: value.update(seed=-1), "seed"),
        (lambda value: value.update(repetition=0), "repetition"),
        (lambda value: value.update(api_key="not-allowed"), "guardrail only"),
        (lambda value: value.update(harness_id="Bearer token-value"), "guardrail only"),
        (lambda value: value.update(harness_id="sk-abcdefghijklmnop"), "guardrail only"),
        (lambda value: value.update(harness_id="ghp_" + "a" * 36), "guardrail only"),
        (lambda value: value.update(harness_id="AKIA" + "A" * 16), "guardrail only"),
        (lambda value: value.update(harness_id="eyJsynthetic.payloadseg.signature"), "guardrail only"),
        (lambda value: value.update(harness_id="glpat-" + "a" * 20), "guardrail only"),
    ],
)
def test_invalid_configs_fail_clearly(tmp_path, mutate, expected):
    (tmp_path / "source.txt").write_text("fixture", encoding="utf-8")
    value = config()
    mutate(value)
    with pytest.raises(ValueError, match=expected):
        manifest.build_manifest(value, tmp_path)


def test_cli_is_repeatedly_stable(tmp_path):
    (tmp_path / "source.txt").write_bytes("東京".encode("utf-8"))
    config_path = tmp_path / "run.json"
    config_path.write_text(json.dumps(config(), ensure_ascii=False), encoding="utf-8")
    command = [sys.executable, str(MODULE_PATH), str(config_path)]
    first = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
    second = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")

    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["run_id"]
