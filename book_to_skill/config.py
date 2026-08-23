import os
import tempfile
from pathlib import Path

def default_output_dir() -> Path:
    """Per-run work directory, unique to this process.

    The PID is part of the name so two extractions running at the same time
    cannot overwrite each other. Every run previously shared one fixed path
    ($TMPDIR/book_skill_work), so whichever run finished second silently
    replaced the first run's full_text.txt and metadata.json — and an agent
    polling for metadata.json could pick up a *different document's*
    extraction without any error, then build a skill from the wrong source.

    The name is deliberately a sibling of the old fixed path rather than a
    child of it. An older cleanup routine that removes "book_skill_work"
    then simply finds nothing, instead of deleting a live concurrent run.

    BOOK_SKILL_WORKDIR still overrides this completely.
    """
    return Path(tempfile.gettempdir()) / f"book_skill_work-{os.getpid()}"


# `or` rather than a get() default: BOOK_SKILL_WORKDIR set to an empty string
# would otherwise become Path(""), i.e. the current directory — which the run
# would then populate and chmod to 0700.
OUTPUT_DIR = Path(os.environ.get("BOOK_SKILL_WORKDIR") or default_output_dir())
OUTPUT_TEXT = OUTPUT_DIR / "full_text.txt"
OUTPUT_META = OUTPUT_DIR / "metadata.json"

WORDS_PER_TOKEN = 0.75  # approximate (Latin / whitespace-delimited text)
# CJK scripts carry little or no whitespace, so word-splitting under-counts them
# by orders of magnitude. Count CJK codepoints directly against this
# chars-per-token ratio instead (see estimate_tokens in utils.py).
CJK_CHARS_PER_TOKEN = 1.5  # approximate for cl100k-style tokenizers

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
    "trafilatura": "trafilatura",
}


def supported_formats_message() -> str:
    return ", ".join(sorted(SUPPORTED_EXTENSIONS))
