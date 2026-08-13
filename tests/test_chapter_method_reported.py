"""The run must say which method produced `chapters_detected`.

Chapter detection picks between counting numeric "Chapter N" headings and
falling back to structural Markdown headings. The two disagree often, and a
wrong count is invisible in the output it produces — it becomes Step 3's plan
and the generated skill's chapter files.

Every parser in this project already announces its method ("Trying
python-docx... OK", "[warn] extract_with_pdftotext failed"). This decision has
the same shape and was the only silent one.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import detect_structure

CHAPTER_BODY = "prose carrying the section's actual content. " * 40


class TestMethodIsReported:
    def test_numeric_headings_report_numeric(self):
        text = "\n\n".join(f"Chapter {n}: Title {n}\n{CHAPTER_BODY}" for n in (1, 2, 3))

        result = detect_structure(text)

        assert result["chapters_detected"] == 3
        assert result["chapters_method"] == "numeric"

    def test_markdown_headings_report_structural(self):
        text = "# Book\n\n" + "\n\n".join(
            f"## Section {n}\n{CHAPTER_BODY}" for n in (1, 2, 3)
        )

        result = detect_structure(text)

        assert result["chapters_detected"] == 3
        assert result["chapters_method"] == "structural"

    def test_no_structure_reports_none(self):
        result = detect_structure("just prose, no headings at all.\n" * 20)

        assert result["chapters_detected"] == 0
        assert result["chapters_method"] == "none"

    def test_method_accompanies_every_count(self):
        """Whatever the input, the pair is always present and consistent."""
        for text in ("", "# Only\n\ntext\n", "Chapter 1: One\n" + CHAPTER_BODY):
            result = detect_structure(text)

            assert "chapters_method" in result
            if result["chapters_detected"] == 0:
                assert result["chapters_method"] == "none"
            else:
                assert result["chapters_method"] in {"numeric", "structural"}
