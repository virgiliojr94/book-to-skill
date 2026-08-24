#!/usr/bin/env python3
"""Build the deterministic, experiment-only PD-03 paper-flat skill pack.

Usage: python3 tools/evals/paper_flat.py SOURCE METADATA OUTPUT_DIR
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

_CHAPTER = re.compile(
    r"^(?:#{1,6}\s+.+|(?:chapter|chap\.)\s+(?:\d+|[ivxlcdm]+)\b.*)$", re.IGNORECASE
)


def _chunks(source: str) -> List[str]:
    """Split at chapter headings, or return one whole-source fallback chunk."""
    lines = source.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if _CHAPTER.match(line.rstrip())]
    if not starts:
        return [source]
    return ["".join(lines[start:end]) for start, end in zip(starts, starts[1:] + [len(lines)])]


def _metadata(path: Path, chunk_count: int) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(value.get(key), str) for key in ("title", "description")):
        raise ValueError("metadata requires string title and description")
    chunks = value.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != chunk_count:
        raise ValueError("metadata chunks must match the source chunk count")
    for chunk in chunks:
        if not isinstance(chunk, dict) or not all(isinstance(chunk.get(key), str) for key in ("description", "summary")):
            raise ValueError("each metadata chunk requires string description and summary")
        if "key_elements" in chunk and (
            not isinstance(chunk["key_elements"], list) or not all(isinstance(item, str) for item in chunk["key_elements"])
        ):
            raise ValueError("key_elements must be a list of strings")
    return value


def build_paper_flat(source_path: Path, metadata_path: Path, output_dir: Path) -> List[Path]:
    """Write a one-level paper-flat pack and return its files in stable order."""
    source = source_path.read_text(encoding="utf-8")
    chunks = _chunks(source)
    metadata = _metadata(metadata_path, len(chunks))
    chunk_dir = output_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    written = []
    for number, (payload, details) in enumerate(zip(chunks, metadata["chunks"]), 1):
        relative = f"chunks/chunk-{number:02d}.md"
        path = output_dir / relative
        with path.open("w", encoding="utf-8", newline="\n") as file:
            file.write(payload)
        written.append(path)
        elements = ", ".join(details.get("key_elements", [])) or "—"
        rows.append(f"| `{relative}` | {details['description']} | {details['summary']} | {elements} |")

    root = "\n".join(
        [
            f"# {metadata['title']}",
            "",
            metadata["description"],
            "",
            "## Activation-time chunk table",
            "",
            "| Path | Description | SUMMARY | KEY_ELEMENTS |",
            "| --- | --- | --- | --- |",
            *rows,
            "",
            "Split policy: source chapter headings; without headings, one full-source chunk.",
            "",
        ]
    )
    root_path = output_dir / "SKILL.md"
    with root_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write(root)
    return [root_path, *written]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an experiment-only PD-03 paper-flat pack.")
    parser.add_argument("source", type=Path, help="UTF-8 synthetic source text")
    parser.add_argument("metadata", type=Path, help="fixed UTF-8 JSON metadata")
    parser.add_argument("output", type=Path, help="output pack directory")
    args = parser.parse_args()
    build_paper_flat(args.source, args.metadata, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
