"""Tests for the experiment-only PD-03 paper-flat pack builder."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "evals" / "paper_flat.py"
SPEC = importlib.util.spec_from_file_location("paper_flat", MODULE_PATH)
paper_flat = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = paper_flat
SPEC.loader.exec_module(paper_flat)
FIXTURES = ROOT / "evals" / "fixtures"


def build(tmp_path, source=FIXTURES / "pd03-book.txt", metadata=FIXTURES / "pd03-metadata.json"):
    return paper_flat.build_paper_flat(source, metadata, tmp_path / "pack")


def test_root_and_raw_chunks_have_expected_one_level_structure(tmp_path):
    build(tmp_path)
    pack = tmp_path / "pack"
    assert (pack / "SKILL.md").read_text(encoding="utf-8") == """# Synthetic Reliability Notes

A synthetic handbook used only to evaluate one-level chunk routing.

## Activation-time chunk table

| Path | Description | SUMMARY | KEY_ELEMENTS |
| --- | --- | --- | --- |
| `chunks/chunk-01.md` | Observe system signals. | Measure before changing. | signal, evidence window |
| `chunks/chunk-02.md` | Respond after observation. | Use the smallest safe response. | — |

Split policy: source chapter headings; without headings, one full-source chunk.
"""
    assert (pack / "chunks" / "chunk-01.md").read_text(encoding="utf-8") == "Chapter 1: Observe\n\nMeasure a signal before changing a system. Record the evidence window.\n\n"
    assert (pack / "chunks" / "chunk-02.md").read_text(encoding="utf-8") == "Chapter 2: Respond\n\nApply the smallest safe response after observation. Verify the result.\n"


def test_identical_inputs_produce_byte_identical_output(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    paper_flat.build_paper_flat(FIXTURES / "pd03-book.txt", FIXTURES / "pd03-metadata.json", first)
    paper_flat.build_paper_flat(FIXTURES / "pd03-book.txt", FIXTURES / "pd03-metadata.json", second)
    assert {path.relative_to(first): path.read_bytes() for path in first.rglob("*") if path.is_file()} == {
        path.relative_to(second): path.read_bytes() for path in second.rglob("*") if path.is_file()
    }


def test_source_chapter_headings_determine_chunks(tmp_path):
    build(tmp_path)
    chunks = sorted((tmp_path / "pack" / "chunks").iterdir())
    assert len(chunks) == 2
    assert all(chunk.read_text(encoding="utf-8").startswith(f"Chapter {number}") for number, chunk in enumerate(chunks, 1))


def test_indented_hash_code_line_does_not_split_chunks():
    source = "# Top-level\n\n    # Code comment\n\nChapter 2: Next\n"

    assert paper_flat._chunks(source) == ["# Top-level\n\n    # Code comment\n\n", "Chapter 2: Next\n"]


def test_no_heading_uses_one_full_source_chunk(tmp_path):
    source = tmp_path / "source.txt"
    metadata = tmp_path / "metadata.json"
    source.write_text("Plain synthetic source.\n", encoding="utf-8")
    metadata.write_text(json.dumps({"title": "Plain", "description": "Fallback fixture.", "chunks": [{"description": "Whole source.", "summary": "No headings."}]}), encoding="utf-8")
    build(tmp_path, source, metadata)
    assert (tmp_path / "pack" / "chunks" / "chunk-01.md").read_text(encoding="utf-8") == "Plain synthetic source.\n"


def test_pack_has_no_child_skill_hierarchy(tmp_path):
    build(tmp_path)
    files = sorted(path.relative_to(tmp_path / "pack") for path in (tmp_path / "pack").rglob("*") if path.is_file())
    assert files == [Path("SKILL.md"), Path("chunks/chunk-01.md"), Path("chunks/chunk-02.md")]
    assert all(path.name == "SKILL.md" for path in files if path.name == "SKILL.md")
