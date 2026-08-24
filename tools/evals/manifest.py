#!/usr/bin/env python3
"""Create deterministic, secret-free manifests for evaluation runs.

Usage: python3 tools/evals/manifest.py config.json [--output manifest.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "pd-run-manifest/v1"
_REQUIRED = {
    "condition", "question_set_hash", "models", "harness_id", "prompt_hashes",
    "config_hashes", "seed", "repetition", "budgets", "artifacts", "results",
    "reason", "decision",
}
_SECRET_MARKERS = ("secret", "password", "credential", "authorization", "api_key", "private_key")
_SECRET_VALUE_PATTERNS = (
    re.compile(r"^Bearer\s+\S+$", re.IGNORECASE),
    re.compile(r"^sk-[A-Za-z0-9_-]{16,}$"),
    re.compile(r"^ghp_[A-Za-z0-9]{36}$"),
    re.compile(r"^AKIA[A-Z0-9]{16}$"),
    re.compile(r"^eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$"),
    re.compile(r"^glpat-[A-Za-z0-9_-]{20}$"),
)
_SECRET_GUARDRAIL = "possible secret (guardrail only; not a DLP guarantee); store only identifiers or hashes"


def canonical_json(value: Any) -> str:
    """Return the UTF-8-preserving canonical JSON representation of *value*."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file's raw bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fail(message: str) -> None:
    raise ValueError(f"invalid run manifest config: {message}")


def _reject_secrets(value: Any, location: str = "config") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail(f"{location} has a non-string key")
            if any(marker in key.lower() for marker in _SECRET_MARKERS):
                _fail(f"{location}.{key} {_SECRET_GUARDRAIL}")
            _reject_secrets(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secrets(child, f"{location}[{index}]")
    elif isinstance(value, str) and any(pattern.fullmatch(value) for pattern in _SECRET_VALUE_PATTERNS):
        _fail(f"{location} {_SECRET_GUARDRAIL}")


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{name} must be a non-empty string")
    return value


def _hashes(value: Any, name: str) -> Dict[str, str]:
    if not isinstance(value, dict) or not value:
        _fail(f"{name} must be a non-empty object of named hashes")
    return {str(key): _identifier(digest, f"{name}.{key}") for key, digest in value.items()}


def _supportable(value: Any, name: str, minimum: int) -> Any:
    if value == "unsupported":
        return value
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if minimum else "non-negative"
        _fail(f"{name} must be {qualifier} integer or 'unsupported'")
    return value


def _budgets(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        _fail("budgets must be an object")
    required = ("max_calls", "max_input_tokens", "max_output_tokens")
    missing = [key for key in required if key not in value]
    if missing:
        _fail("budgets missing " + ", ".join(missing))
    result: Dict[str, Any] = {}
    for key in required:
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            _fail(f"budgets.{key} must be a non-negative integer hard ceiling")
        result[key] = item
    if "max_cost_usd" in value:
        cost = value["max_cost_usd"]
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
            _fail("budgets.max_cost_usd must be a non-negative finite number")
        result["max_cost_usd"] = cost
    return result


def _commit(base_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=base_dir, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unavailable"


def build_manifest(config: Dict[str, Any], base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Validate *config*, hash its sources, and return a deterministic manifest."""
    if not isinstance(config, dict):
        _fail("top level must be an object")
    _reject_secrets(config)
    missing = sorted(_REQUIRED - set(config))
    if missing:
        _fail("missing required fields: " + ", ".join(missing))
    base_dir = (base_dir or Path.cwd()).resolve()
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        _fail("sources must be a non-empty list")
    source_records = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            _fail(f"sources[{index}] must be an object")
        source_id = _identifier(source.get("id"), f"sources[{index}].id")
        source_path = _identifier(source.get("path"), f"sources[{index}].path")
        resolved = (base_dir / source_path).resolve()
        if not resolved.is_file():
            _fail(f"sources[{index}].path is not a readable file: {source_path}")
        source_records.append({"id": source_id, "sha256": sha256_file(resolved)})
    source_records.sort(key=lambda record: (record["id"], record["sha256"]))

    models = config["models"]
    if not isinstance(models, dict) or not models:
        _fail("models must be a non-empty object")
    normalized_models = {str(key): _identifier(value, f"models.{key}") for key, value in models.items()}
    artifacts = _identifier(config["artifacts"], "artifacts")
    results = _identifier(config["results"], "results")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "sources": source_records,
        "condition": _identifier(config["condition"], "condition"),
        "question_set_hash": _identifier(config["question_set_hash"], "question_set_hash"),
        "models": normalized_models,
        "harness_id": _identifier(config["harness_id"], "harness_id"),
        "prompt_hashes": _hashes(config["prompt_hashes"], "prompt_hashes"),
        "config_hashes": _hashes(config["config_hashes"], "config_hashes"),
        "seed": _supportable(config["seed"], "seed", 0),
        "repetition": _supportable(config["repetition"], "repetition", 1),
        "budgets": _budgets(config["budgets"]),
        "commit": _commit(base_dir),
        "artifacts": artifacts,
        "results": results,
        "reason": _identifier(config["reason"], "reason"),
        "decision": _identifier(config["decision"], "decision"),
    }
    identity = {key: value for key, value in manifest.items() if key not in {"artifacts", "results"}}
    if manifest["commit"] == "unavailable":
        identity.pop("commit")
    manifest["run_id"] = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="evaluation run config JSON")
    parser.add_argument("--output", type=Path, help="write manifest JSON to this file")
    args = parser.parse_args(argv)
    try:
        with args.config.open(encoding="utf-8") as stream:
            config = json.load(stream)
        rendered = canonical_json(build_manifest(config, args.config.parent)) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
