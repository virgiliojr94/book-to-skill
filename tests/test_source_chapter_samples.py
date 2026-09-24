"""The CLI must retain the heading samples it already extracted per source."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import detect_structure, extract_single_file


def _numbered_book(title):
    return "\n\n".join(
        f"# Chapter {number}: {title} {number}\nBody for this chapter."
        for number in range(1, 13)
    )


ALPHA = _numbered_book("Alpha")
BETA = _numbered_book("Beta")
PLAIN = "Ordinary prose without any chapter headings.\n"
STRUCTURAL = "# Book\n\n## First topic\nBody one.\n\n## Second topic\nBody two.\n"
UNICODE = "第一章 緒論\n\nBody one.\n\n第二章 架構\n\nBody two.\n"


@pytest.mark.parametrize(
    "texts,expected_samples",
    [
        ([ALPHA], [[f"# Chapter {n}: Alpha {n}" for n in range(1, 11)]]),
        (
            [ALPHA, BETA],
            [[f"# Chapter {n}: {title} {n}" for n in range(1, 11)]
             for title in ("Alpha", "Beta")],
        ),
        (
            [BETA, ALPHA],
            [[f"# Chapter {n}: {title} {n}" for n in range(1, 11)]
             for title in ("Beta", "Alpha")],
        ),
        ([PLAIN, STRUCTURAL], [[], []]),
        ([UNICODE], [["第一章 緒論", "第二章 架構"]]),
    ],
    ids=["single", "multi", "reversed", "empty-samples", "unicode"],
)
def test_cli_preserves_source_chapter_samples(tmp_path, texts, expected_samples):
    paths = []
    for index, text in enumerate(texts):
        path = tmp_path / f"source{index}.md"
        path.write_text(text, encoding="utf-8")
        paths.append(path)

    extracted = [extract_single_file(path, "text", "no") for path in paths]
    # Establish the input-side contract independently of the JSON projection.
    assert [src["chapter_headings_sample"] for src in extracted] == expected_samples

    workdir = tmp_path / "output"
    env = dict(os.environ, BOOK_SKILL_WORKDIR=str(workdir))
    proc = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "extract.py"),
         *map(str, paths), "--mode", "text", "--install-missing", "no"],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["total_sources"] == len(paths)
    assert [src["chapter_headings_sample"] for src in metadata["sources"]] == expected_samples

    # The added field must not change source counts or consolidated detection.
    for saved, original in zip(metadata["sources"], extracted):
        for key in ("source_file", "chapters_detected", "chapters_method", "has_toc"):
            assert saved[key] == original[key]
    consolidated = detect_structure("\n\n".join(src["text"] for src in extracted))
    for key in ("chapters_detected", "chapters_method", "chapter_headings_sample"):
        assert metadata[key] == consolidated[key]
    output_text = (workdir / "full_text.txt").read_text(encoding="utf-8")
    for src in extracted:
        assert src["text"].strip() in output_text
