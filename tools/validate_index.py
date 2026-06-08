#!/usr/bin/env python3
"""
validate_index.py — check a generated skill's index.json for integrity.

A skill's index.json (Step 9.5) is what lets the agent resolve a topic to its
chapter file in one hop. If it drifts from the files on disk, that lookup breaks
silently. This validator catches the drift.

Checks:
  1. index.json is valid JSON with the required keys
  2. every chapter `file` exists on disk
  3. every chapter id referenced in `topics` exists in `chapters`
  4. topic keys are lowercase
  5. (warning) every chapter is reachable from at least one topic

Usage:
  python3 tools/validate_index.py <skill_dir>
Exit code 0 = valid, 1 = errors found.
"""

import json
import sys
from pathlib import Path

REQUIRED_KEYS = {"skill", "title", "chapters", "topics"}


def validate(skill_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    idx_path = skill_dir / "index.json"
    if not idx_path.is_file():
        return ([f"index.json not found in {skill_dir}"], [])

    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ([f"index.json is not valid JSON: {exc}"], [])

    missing_keys = REQUIRED_KEYS - idx.keys()
    if missing_keys:
        errors.append(f"missing required keys: {', '.join(sorted(missing_keys))}")
        return (errors, warnings)

    chapters = idx.get("chapters", [])
    chapter_ids: set[str] = set()
    for ch in chapters:
        n = ch.get("n")
        cid = f"ch{int(n):02d}" if isinstance(n, int) else None
        if cid:
            chapter_ids.add(cid)
        file_rel = ch.get("file")
        if not file_rel:
            errors.append(f"chapter {n} has no 'file'")
            continue
        if not (skill_dir / file_rel).is_file():
            errors.append(f"chapter {n}: file does not exist on disk: {file_rel}")

    topics = idx.get("topics", {})
    referenced: set[str] = set()
    for topic, refs in topics.items():
        if topic != topic.lower():
            errors.append(f"topic key not lowercase: '{topic}'")
        if not isinstance(refs, list):
            errors.append(f"topic '{topic}' must map to a list of chapter ids")
            continue
        for ref in refs:
            referenced.add(ref)
            if ref not in chapter_ids:
                errors.append(f"topic '{topic}' references unknown chapter '{ref}'")

    unreachable = chapter_ids - referenced
    if unreachable:
        warnings.append(f"chapters not reachable from any topic: {', '.join(sorted(unreachable))}")

    return (errors, warnings)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_index.py <skill_dir>", file=sys.stderr)
        return 2

    skill_dir = Path(sys.argv[1])
    errors, warnings = validate(skill_dir)

    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        for e in errors:
            print(f"  ERROR {e}")
        print(f"\n✗ index.json invalid: {len(errors)} error(s)")
        return 1

    print(f"✓ index.json valid ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
