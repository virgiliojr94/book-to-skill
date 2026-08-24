#!/usr/bin/env python3
"""Replay a versioned synthetic trajectory fixture deterministically."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from score import score

SCHEMA_VERSION = "pd-replay-fixture/v1"
RESULT_SCHEMA_VERSION = "pd-replay-result/v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def load_fixture(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        fixture = json.load(source)
    if fixture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported fixture schema_version")
    trajectories = fixture.get("trajectories")
    if not isinstance(trajectories, list):
        raise ValueError("fixture trajectories must be a list")
    return fixture


def replay(path: Path) -> Dict[str, Any]:
    fixture = load_fixture(path)
    result = score(fixture["trajectories"])
    return {"schema_version": RESULT_SCHEMA_VERSION, "fixture_version": fixture["fixture_version"], **result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    print(canonical_json(replay(args.fixture)))


if __name__ == "__main__":
    main()
