from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from book_to_skill.exceptions import ExtractionError


MAX_ARCHIVE_MEMBERS = 10_000
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


class BoundedZipFile(ZipFile):
    """Reject oversized document archives and bound bytes read from each one."""

    def __init__(self, file: str | Path) -> None:
        super().__init__(file)
        try:
            members = self.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise ExtractionError(
                    f"Archive member count exceeds limit of {MAX_ARCHIVE_MEMBERS:,}."
                )
            total = 0
            for member in members:
                # Other codecs can expand unboundedly inside ZipExtFile.read().
                if member.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
                    raise ExtractionError(
                        "Archive compression must use stored or deflated members."
                    )
                if member.file_size > MAX_MEMBER_BYTES:
                    raise ExtractionError(
                        f"Archive member size exceeds limit of {MAX_MEMBER_BYTES:,} bytes."
                    )
                total += member.file_size
                if total > MAX_TOTAL_BYTES:
                    raise ExtractionError(
                        f"Archive expanded size exceeds limit of {MAX_TOTAL_BYTES:,} bytes."
                    )
        except ExtractionError:
            self.close()
            raise
        self._remaining_bytes = MAX_TOTAL_BYTES

    def read(self, name: str | ZipInfo, pwd: bytes | None = None) -> bytes:
        limit = min(MAX_MEMBER_BYTES, self._remaining_bytes)
        with self.open(name, pwd=pwd) as member:
            data = member.read(limit + 1)
        if len(data) > limit:
            raise ExtractionError(
                "Archive decompressed bytes exceed the member or total read limit."
            )
        self._remaining_bytes -= len(data)
        return data
