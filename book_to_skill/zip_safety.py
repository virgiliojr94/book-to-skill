"""Resource limits for ZIP-based input formats such as EPUB and DOCX."""

import zipfile

from book_to_skill.exceptions import ExtractionError


MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_TOTAL_SIZE = 512 * 1024 * 1024
MAX_ZIP_MEMBER_SIZE = 128 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 100


def validate_zip_archive(archive: zipfile.ZipFile, format_name: str) -> None:
    """Reject archives whose declared expansion would exceed safe limits."""
    members = archive.infolist()
    if len(members) > MAX_ZIP_ENTRIES:
        raise ExtractionError(
            f"Unsafe {format_name}: archive has {len(members):,} entries "
            f"(maximum {MAX_ZIP_ENTRIES:,})."
        )

    total_size = 0
    for member in members:
        if member.file_size > MAX_ZIP_MEMBER_SIZE:
            raise ExtractionError(
                f"Unsafe {format_name}: '{member.filename}' expands to "
                f"{member.file_size:,} bytes (maximum {MAX_ZIP_MEMBER_SIZE:,})."
            )
        if member.compress_size and member.file_size / member.compress_size > MAX_ZIP_COMPRESSION_RATIO:
            raise ExtractionError(
                f"Unsafe {format_name}: '{member.filename}' exceeds the "
                f"maximum compression ratio of {MAX_ZIP_COMPRESSION_RATIO}:1."
            )
        total_size += member.file_size
        if total_size > MAX_ZIP_TOTAL_SIZE:
            raise ExtractionError(
                f"Unsafe {format_name}: archive expands to more than "
                f"{MAX_ZIP_TOTAL_SIZE // (1024 * 1024)} MiB."
            )
