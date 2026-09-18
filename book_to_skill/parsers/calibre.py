from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from book_to_skill.config import OUTPUT_DIR
from book_to_skill.exceptions import ExtractionError


def extract_with_ebook_convert(input_path: str) -> str | None:
    if not shutil.which("ebook-convert"):
        return None

    # Each call converts into its own temporary directory under OUTPUT_DIR. The
    # work directory is shared by every source in a batch — and by separate runs
    # whenever BOOK_SKILL_WORKDIR is set explicitly — so any output reachable by
    # a predictable name can be satisfied by an earlier run's leftover: a
    # conversion that reports success without writing anything would return that
    # earlier file's text and record it under the current source's name. A
    # per-pid counter is not enough, because a reused pid across two interpreters
    # collapses back to the same name; a fresh TemporaryDirectory is
    # unaddressable from outside this call. Cleanup on exit also stops one full
    # intermediate text per source from piling up in the work directory.
    #
    # A directory that cannot be created is raised, not swallowed: returning None
    # here would be indistinguishable from "converted fine, wrote nothing", which
    # is exactly the silent-failure shape this function is meant to refuse.
    try:
        tmp_ctx = tempfile.TemporaryDirectory(dir=OUTPUT_DIR, prefix="ebook-convert-")
    except OSError as e:
        raise ExtractionError(
            f"cannot create a conversion directory under {OUTPUT_DIR}: {e}"
        ) from e

    with tmp_ctx as tmp_name:
        output_path = Path(tmp_name) / "ebook-convert-output.txt"
        try:
            input_path = os.path.abspath(input_path)
            result = subprocess.run(
                ["ebook-convert", input_path, str(output_path)],
                capture_output=True, text=True, timeout=300
            )
            # Read before the with-block exits: cleanup deletes the directory.
            if result.returncode == 0 and output_path.exists():
                text = output_path.read_text(encoding="utf-8", errors="replace")
                if text.strip():
                    return text
        except Exception as e:
            print(f"  [warn] extract_with_ebook_convert failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None
