from __future__ import annotations

import os
import shutil
import subprocess
import sys
import hashlib
from book_to_skill.config import OUTPUT_DIR


def extract_with_ebook_convert(input_path: str) -> str | None:
    if not shutil.which("ebook-convert"):
        return None
    
    # Compute a unique hash to prevent race conditions during parallel runs
    path_hash = hashlib.md5(input_path.encode("utf-8", errors="replace")).hexdigest()
    output_path = OUTPUT_DIR / f"ebook-convert-output-{path_hash}.txt"
    
    try:
        input_path = os.path.abspath(input_path)
        result = subprocess.run(
            ["ebook-convert", input_path, str(output_path)],
            capture_output=True, text=True, timeout=300
        )
        text = None
        if result.returncode == 0 and output_path.exists():
            text = output_path.read_text(encoding="utf-8", errors="replace")
            
        # Clean up temporary file to keep output directory tidy
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass
                
        if text and text.strip():
            return text
    except Exception as e:
        print(f"  [warn] extract_with_ebook_convert failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None
