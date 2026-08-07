from __future__ import annotations

import json
import shutil
import subprocess
from typing import Tuple

from book_to_skill.exceptions import ExtractionError


def _find_node_cmd() -> str | None:
    # prefer node in PATH; npx can be used as an alternative when invoking npx
    return shutil.which("node") or shutil.which("npx")


def extract_with_anydoc(path: str, timeout: int = 120) -> Tuple[str, str]:
    """
    Calls scripts/anydoc_extractor.js <path> and returns (text, method).
    Raises ExtractionError on failure.
    """
    node = _find_node_cmd()
    if not node:
        raise ExtractionError("Node.js (or npx) not found on PATH; anydoc requires Node.js.")
    # Prefer invoking node directly for the local script
    cmd = [node, "scripts/anydoc_extractor.js", path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        raise ExtractionError(f"Failed to run anydoc extractor: {exc}")
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise ExtractionError(f"anydoc extractor failed: {stderr or 'exit code ' + str(proc.returncode)}")
    # Try to parse JSON output; accept plain text as fallback
    out = proc.stdout.strip()
    if not out:
        return "", "anydoc"
    try:
        payload = json.loads(out)
    except Exception:
        # Not JSON — assume the whole stdout is the extracted text
        return out, "anydoc"
    text = payload.get("text") or payload.get("content") or payload.get("body") or ""
    return text, "anydoc"
