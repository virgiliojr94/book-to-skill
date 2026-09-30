"""Structural chapter counts exclude book framing and report their evidence."""

from book_to_skill.utils import _structural_chapter_count, detect_structure


def _book(chapter_count: int) -> str:
    headings = [
        "## Preface",
        "## Foreword",
        "## Acknowledgements",
        "## Acknowledgments",
        "## Dedication",
        "## Copyright",
        "## Epigraph",
        "## Prologue",
        "## Table of Contents",
        *(f"## Chapter Title {number}" for number in range(1, chapter_count + 1)),
        "## Appendix A: Notation",
        "## Appendices B: Datasets",
        "## Glossary",
        "## Bibliography",
        "## References",
        "## Works Cited",
        "## Further Reading",
        "## Index",
        "## Notes",
        "## Endnotes",
        "## Footnotes",
        "## Colophon",
        "## About the Author",
        "## About the Authors",
    ]
    return "# Synthetic Book\n\n" + "\n\n".join(
        f"{heading}\nInstructional body." for heading in headings
    )


def test_framing_sections_are_excluded_and_structural_sample_is_populated():
    result = detect_structure(_book(5))

    assert result["chapters_detected"] == 5
    assert result["chapters_method"] == "structural"
    assert result["chapter_headings_sample"] == [
        f"## Chapter Title {number}" for number in range(1, 6)
    ]


def test_twenty_chapters_are_not_inflated_by_framing_sections():
    result = detect_structure(_book(20))

    assert result["chapters_detected"] == 20
    assert result["chapter_headings_sample"] == [
        f"## Chapter Title {number}" for number in range(1, 11)
    ]


def test_whole_title_and_word_boundary_guards_keep_instructional_titles():
    titles = [
        "Introduction",
        "Indexing Strategies",
        "Glossary of Terms",
        "Building an Index",
        "Bibliography Management",
        "Notes on Design",
        "References in Practice",
        "Partnership Models",
        "Appendixology for Engineers",
    ]
    text = "\n\n".join(f"## {title}\nInstructional body." for title in titles)

    result = detect_structure(text)

    assert result["chapters_detected"] == len(titles)
    assert result["chapter_headings_sample"] == [f"## {title}" for title in titles]


def test_bare_appendix_and_labelled_part_are_not_chapters():
    text = """# Course

# Part I: Foundations

## First Topic
Instructional body.

## Appendix
Reference tables.

# Part II: Practice

## Second Topic
Instructional body.
"""

    assert _structural_chapter_count(text) == 2


def test_setext_framing_sections_are_filtered_too():
    text = """Preface
-------
Front matter.

First Topic
-----------
Instructional body.

Second Topic
------------
Instructional body.

Bibliography
------------
References.
"""

    result = detect_structure(text)

    assert result["chapters_detected"] == 2
    assert result["chapter_headings_sample"] == ["First Topic", "Second Topic"]
