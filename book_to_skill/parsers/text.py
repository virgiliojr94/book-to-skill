from __future__ import annotations
import sys
from pathlib import Path


def read_text_file(path: str) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return Path(path).read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  [warn] read_text_file failed: {type(e).__name__}: {e}", file=sys.stderr)
            return None
    return None
