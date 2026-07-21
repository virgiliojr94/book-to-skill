import os
import tempfile
from pathlib import Path

# An explicitly supplied directory is useful for integrations that need a
# stable destination.  Otherwise, create an isolated workspace for this run.
# A fixed path in the system temporary directory allowed concurrent invocations
# to overwrite one another's ``full_text.txt`` and ``metadata.json`` files.
_configured_workdir = os.environ.get("BOOK_SKILL_WORKDIR")
OUTPUT_DIR = (
    Path(_configured_workdir)
    if _configured_workdir
    else Path(tempfile.mkdtemp(prefix="book-to-skill-"))
)
OUTPUT_TEXT = OUTPUT_DIR / "full_text.txt"
OUTPUT_META = OUTPUT_DIR / "metadata.json"
OUTPUT_MANIFEST = OUTPUT_DIR / "manifest.json"
TOOL_VERSION = "1.2.0"

WORDS_PER_TOKEN = 0.75  # approximate

# Resource ceilings for untrusted documents.  They can be raised deliberately
# by an integrator that has appropriate infrastructure and monitoring.
MAX_INPUT_FILE_SIZE = 512 * 1024 * 1024
MAX_INPUT_FILES = 1_000
MAX_EXTRACTED_TEXT_CHARS = 100 * 1024 * 1024
MAX_CONSOLIDATED_TEXT_CHARS = 200 * 1024 * 1024

TEXT_EXTENSIONS = {".txt", ".text", ".md", ".markdown", ".rst", ".adoc", ".asciidoc"}
HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
CALIBRE_EBOOK_EXTENSIONS = {".mobi", ".azw", ".azw3"}
SUPPORTED_EXTENSIONS = {
    ".pdf", ".epub", ".docx", ".rtf",
    *TEXT_EXTENSIONS,
    *HTML_EXTENSIONS,
    *CALIBRE_EBOOK_EXTENSIONS,
}

PYTHON_DEPENDENCIES = {
    "docling": "docling",
    "pypdf": "pypdf",
    "pdfminer": "pdfminer.six",
    "ebooklib": "ebooklib",
    "bs4": "beautifulsoup4",
    "docx": "python-docx",
    "striprtf": "striprtf",
}


def supported_formats_message() -> str:
    return ", ".join(sorted(SUPPORTED_EXTENSIONS))
