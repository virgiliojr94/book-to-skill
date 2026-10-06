"""Structural chapter depth is selected within each source, not across books."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("source_count,include_plain", [(1, False), (3, False), (3, True)])
def test_cli_counts_structural_chapters_below_source_titles(
    tmp_path, source_count, include_plain
):
    paths = []
    expected_headings = []
    for source_number in range(1, source_count + 1):
        path = tmp_path / f"book{source_number}.md"
        headings = [
            f"## Topic {source_number}.{chapter_number}"
            for chapter_number in range(1, 4)
        ]
        path.write_text(
            f"# Book {source_number}\n\n"
            + "\n\n".join(f"{heading}\nBody text." for heading in headings)
            + "\n",
            encoding="utf-8",
        )
        paths.append(path)
        expected_headings.extend(headings)
    if include_plain:
        plain = tmp_path / "notes.md"
        plain.write_text("Supporting prose without chapter headings.\n", encoding="utf-8")
        paths.append(plain)

    workdir = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "scripts" / "extract.py"),
            *map(str, paths),
            "--mode",
            "text",
            "--install-missing",
            "no",
        ],
        env=dict(os.environ, BOOK_SKILL_WORKDIR=str(workdir)),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["chapters_detected"] == 3 * source_count
    assert metadata["chapters_method"] == "structural"
    assert metadata["chapter_headings_sample"] == expected_headings[:10]
    assert [source["chapters_detected"] for source in metadata["sources"]] == (
        [3] * source_count + ([0] if include_plain else [])
    )
