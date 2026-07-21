"""Safe helpers for publishing extraction output."""

import os
import tempfile
from pathlib import Path
from typing import Optional


def atomic_write_text(destination: Path, content: str) -> None:
    """Write UTF-8 text without exposing a partially-written final file.

    The temporary file is created beside the destination so ``os.replace`` is
    atomic on the same filesystem.  A failed write leaves the prior output
    intact and removes its temporary file.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temp_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temp_name, destination)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
