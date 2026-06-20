import sys
import json
import shutil
from pathlib import Path

# Bootstrap: make sure the book_to_skill package is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.glossary_extractor import (
    extract_glossary_data,
    generate_cheatsheet_markdown,
    extract_code_blocks,
)
import book_to_skill.utils as utils


SYNTHETIC_TEXT = """Introduction to the Book
This is a preface section.

Capítulo 1: The Core Concepts
In this chapter, we discuss the AST. The **AST** refers to the Abstract Syntax Tree.
AI refers to Artificial Intelligence. An LLM is a Large Language Model.
We can define B2S as Book to Skill.
The **Discovery Loop Tax** — the token tax incurred when querying an agent multiple times.

Here is a practical code example:
```python
def extract_book(path):
    print("Extracting " + path)
    return "text"
```

Capítulo 2: Advanced Topics
We will also examine RAG. RAG refers to Retrieval-Augmented Generation.
"""


def test_extract_glossary_data_acronyms():
    data = extract_glossary_data(SYNTHETIC_TEXT)
    terms = {t["term"]: t for t in data["terms"]}
    
    # Verify acronyms detected
    assert "AST" in terms
    assert "AI" in terms
    assert "LLM" in terms
    assert "B2S" in terms
    assert "RAG" in terms
    
    # Verify acronym type
    assert terms["AST"]["type"] == "acronym"


def test_extract_glossary_data_bold_patterns():
    data = extract_glossary_data(SYNTHETIC_TEXT)
    terms = {t["term"]: t for t in data["terms"]}
    
    # Verify bold pattern matched
    assert "Discovery Loop Tax" in terms
    assert terms["Discovery Loop Tax"]["type"] == "pattern_bold"
    assert "token tax incurred" in terms["Discovery Loop Tax"]["definition"]


def test_extract_code_blocks():
    blocks = extract_code_blocks(SYNTHETIC_TEXT)
    assert len(blocks) == 1
    assert blocks[0]["language"] == "python"
    assert "def extract_book" in blocks[0]["code"]


def test_generate_cheatsheet_markdown():
    glossary = extract_glossary_data(SYNTHETIC_TEXT)
    markdown = generate_cheatsheet_markdown(SYNTHETIC_TEXT, glossary, "Mock Book")
    
    assert "# Cheatsheet: Mock Book" in markdown
    assert "## Key Acronyms" in markdown
    assert "AST" in markdown
    assert "## Code Snippets & Practical Examples" in markdown
    assert "def extract_book" in markdown


def test_cli_chunk_and_glossary_integration(tmp_path, monkeypatch):
    # Set up temporary output paths to isolate the test execution
    out_dir = tmp_path / "output"
    out_text = out_dir / "full_text.txt"
    out_meta = out_dir / "metadata.json"
    
    monkeypatch.setattr(utils, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(utils, "OUTPUT_TEXT", out_text)
    monkeypatch.setattr(utils, "OUTPUT_META", out_meta)
    
    # Write a test input book
    input_book = tmp_path / "test_book.txt"
    input_book.write_text(SYNTHETIC_TEXT, encoding="utf-8")
    
    # Simulate CLI arguments: extract.py <book> --chunk --extract-glossary
    argv = [
        "extract.py",
        str(input_book),
        "--chunk",
        "--extract-glossary"
    ]
    
    old_argv = sys.argv
    sys.argv = argv
    try:
        utils.main()
    finally:
        sys.argv = old_argv
        
    # Verify global outputs
    assert out_text.exists()
    assert out_meta.exists()
    
    glossary_file = out_dir / "glossary.json"
    cheatsheet_file = out_dir / "cheatsheet.md"
    assert glossary_file.exists()
    assert cheatsheet_file.exists()
    
    # Verify glossary content
    glossary_data = json.loads(glossary_file.read_text(encoding="utf-8"))
    terms = {t["term"] for t in glossary_data["terms"]}
    assert "AST" in terms
    
    # Verify chunk structure
    chunks_dir = out_dir / "chunks"
    assert chunks_dir.exists()
    
    manifest_file = chunks_dir / "manifest.json"
    assert manifest_file.exists()
    
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest_data["total_chunks"] == 3  # Preface, Chapter 1, Chapter 2
    
    # Check that directories exist and have outputs
    chunks = manifest_data["chunks"]
    assert chunks[0]["title"] == "Prefácio / Introdução"
    assert chunks[1]["title"] == "Capítulo 1: The Core Concepts"
    assert chunks[2]["title"] == "Capítulo 2: Advanced Topics"
    
    # Verify the chunk folders contain text.txt, glossary.json and cheatsheet.md
    for chunk in chunks:
        folder_path = chunks_dir / chunk["folder"]
        assert folder_path.exists()
        assert (folder_path / "text.txt").exists()
        assert (folder_path / "glossary.json").exists()
        assert (folder_path / "cheatsheet.md").exists()
        
        # Verify slice bounds
        sliced_text = (folder_path / "text.txt").read_text(encoding="utf-8")
        assert len(sliced_text) > 0
