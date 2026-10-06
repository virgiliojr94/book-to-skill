"""Part labels must not hide the chapters they group (issue #271)."""

import pytest

from book_to_skill.utils import detect_structure


@pytest.mark.parametrize("marker", ["#", "="])
@pytest.mark.parametrize("labels", [("I", "II"), ("1", "2")])
def test_part_labels_do_not_suppress_structural_chapters(marker, labels):
    text = "\n\n".join(
        f"{marker} Part {label}: Group\n\n" + "\n\n".join(
            f"{marker * 2} Topic {n}\nSynthetic chapter body."
            for n in range(start, start + 5)
        )
        for label, start in zip(labels, (1, 6))
    )

    result = detect_structure(text)

    assert result["chapters_detected"] == 10
    assert result["chapters_method"] == "structural"
    assert result["chapter_headings_sample"] == [
        f"{marker * 2} Topic {n}" for n in range(1, 11)
    ]


def test_part_numbers_do_not_inflate_real_numbered_chapters():
    text = "# Part I\n\n# Part II\n\n" + "\n\n".join(
        f"## Chapter {n}: Topic\nSynthetic chapter body."
        for n in (3, 4, 5)
    )

    result = detect_structure(text)

    assert result["chapters_detected"] == 3
    assert result["chapters_method"] == "numeric"
    assert result["chapter_headings_sample"] == [
        f"## Chapter {n}: Topic" for n in (3, 4, 5)
    ]


def test_part_only_plain_text_book_keeps_numeric_fallback():
    result = detect_structure("Part I: Foundations\nBody.\n\nPart II: Practice\nBody.")

    assert result["chapters_detected"] == 2
    assert result["chapters_method"] == "numeric"
    assert result["chapter_headings_sample"] == [
        "Part I: Foundations", "Part II: Practice"
    ]


def test_instructional_titles_beginning_with_part_are_chapters():
    titles = ["Part of Speech", "Part of a Whole", "Partnership Models"]
    text = "\n\n".join(f"## {title}\nSynthetic chapter body." for title in titles)

    result = detect_structure(text)

    assert result["chapters_detected"] == 3
    assert result["chapter_headings_sample"] == [f"## {title}" for title in titles]
