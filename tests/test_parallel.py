import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from book_to_skill.cli import parse_arguments, parse_workers, resolve_input_files
from book_to_skill.parsers.calibre import extract_with_ebook_convert
import book_to_skill.utils as utils


def test_parse_workers():
    # Default is 1
    assert parse_workers(["extract.py", "file.txt"]) == 1
    
    # Custom values
    assert parse_workers(["extract.py", "--workers", "4"]) == 4
    assert parse_workers(["extract.py", "--jobs", "2"]) == 2
    
    # Auto uses cpu count
    cpu_count = os.cpu_count() or 4
    assert parse_workers(["extract.py", "--workers", "auto"]) == cpu_count
    
    # Invalid values default to 1
    assert parse_workers(["extract.py", "--workers", "invalid"]) == 1
    assert parse_workers(["extract.py", "--jobs", "-5"]) == 1


def test_parse_arguments_skips_workers():
    args = ["extract.py", "file1.pdf", "--workers", "4", "file2.epub", "--jobs", "2"]
    input_paths, mode, install = parse_arguments(args)
    # The --workers/--jobs and their arguments should be omitted from input paths
    assert input_paths == ["file1.pdf", "file2.epub"]


def test_calibre_unique_temp_file():
    # Mock ebook-convert executable presence
    with patch("shutil.which", return_value="/usr/bin/ebook-convert"), \
         patch("subprocess.run") as mock_run:
         
        mock_run.return_value = MagicMock(returncode=0)
        
        # We need to make sure the unique path matches and is deleted
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="Calibre text content"), \
             patch("pathlib.Path.unlink") as mock_unlink:
             
            res = extract_with_ebook_convert("my_book.mobi")
            assert res == "Calibre text content"
            
            # Subprocess should have been called with a unique hash in output path name
            called_args = mock_run.call_args[0][0]
            assert any("ebook-convert-output-" in arg for arg in called_args)
            
            # Temporary file should have been cleaned up
            mock_unlink.assert_called_once()


def test_parallel_execution_preserves_order(tmp_path, capsys):
    # Create 3 small text files
    files = []
    for i in range(3):
        p = tmp_path / f"book_{i}.txt"
        p.write_text(f"Chapter 1\nContent of book {i}", encoding="utf-8")
        files.append(p)
        
    # Let's run cli.main through mock arguments
    import book_to_skill.cli as cli
    
    test_argv = ["extract.py", *[str(f) for f in files], "--workers", "3", "--no-cache"]
    
    out_dir = tmp_path / "output"
    out_text = out_dir / "full_text.txt"
    out_meta = out_dir / "metadata.json"
    
    with patch("sys.argv", test_argv), \
         patch("book_to_skill.utils.OUTPUT_DIR", out_dir), \
         patch("book_to_skill.utils.OUTPUT_TEXT", out_text), \
         patch("book_to_skill.utils.OUTPUT_META", out_meta):
         
        cli.main()
        
        # Check that outputs are created
        assert out_text.exists()
        assert out_meta.exists()
        
        text_content = out_text.read_text(encoding="utf-8")
        
        # Verify the order of consolidated texts matches the alphabetic input order
        assert "book_0.txt" in text_content
        assert "book_1.txt" in text_content
        assert "book_2.txt" in text_content
        
        pos0 = text_content.find("SOURCE: book_0.txt")
        pos1 = text_content.find("SOURCE: book_1.txt")
        pos2 = text_content.find("SOURCE: book_2.txt")
        
        assert pos0 < pos1 < pos2
