import os
import shutil
from pathlib import Path
import pytest
from book_to_skill.utils import extract_single_file, USE_CACHE, CACHE_DIR
import book_to_skill.utils as utils


def _make_temp_file(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def clean_cache_dir():
    utils.USE_CACHE = True
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    yield
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    utils.USE_CACHE = True


def test_cache_miss_and_hit(tmp_path, capsys):
    f = _make_temp_file(tmp_path, "sample.txt", "Conteúdo de teste para caching.")
    
    # First call: should be Cache Miss
    res1 = extract_single_file(f, "text", "no")
    captured = capsys.readouterr()
    assert "Using cached extraction" not in captured.out
    
    # Check cache file generated
    sha256 = utils._compute_file_sha256(f)
    cache_file = CACHE_DIR / f"{sha256}.json"
    assert cache_file.exists()
    
    # Second call: should be Cache Hit
    res2 = extract_single_file(f, "text", "no")
    captured = capsys.readouterr()
    assert "Using cached extraction" in captured.out
    assert res1["text"] == res2["text"]
    assert res1["estimated_tokens"] == res2["estimated_tokens"]


def test_cache_invalidation_on_content_change(tmp_path, capsys):
    f = _make_temp_file(tmp_path, "sample.txt", "Conteúdo Inicial.")
    
    # First call: Cache Miss
    extract_single_file(f, "text", "no")
    capsys.readouterr()
    
    # Mutate file content (changes SHA-256 hash)
    f.write_text("Conteúdo Modificado.", encoding="utf-8")
    
    # Second call: should be Cache Miss again
    extract_single_file(f, "text", "no")
    captured = capsys.readouterr()
    assert "Using cached extraction" not in captured.out


def test_no_cache_flag(tmp_path, capsys):
    f = _make_temp_file(tmp_path, "sample.txt", "Teste de bypass de cache.")
    utils.USE_CACHE = False
    
    # First call: cache disabled
    extract_single_file(f, "text", "no")
    
    # Check cache file not generated
    sha256 = utils._compute_file_sha256(f)
    cache_file = CACHE_DIR / f"{sha256}.json"
    assert not cache_file.exists()
    
    # Second call: cache disabled
    extract_single_file(f, "text", "no")
    captured = capsys.readouterr()
    assert "Using cached extraction" not in captured.out
