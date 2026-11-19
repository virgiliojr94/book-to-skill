"""Outline chapters whose body headings pdftotext emits letter-spaced.

Word documents with expanded character spacing come out of pdftotext as
``C h ư ơn g 2 1   T i ê u đ ề ...``: letters (even chapter digits) separated by
spaces, irregularly, with the title wrapped onto a second line. The ToC line
carries the same title plus a dashed leader and page number and must not be
taken as the chapter start. Synthetic Vietnamese fixture mirroring that shape
(no source-book text).
"""

from __future__ import annotations

from book_to_skill.utils import chapter_line_ranges

_TITLES = [
    "Chương 1 Nền tảng Quản trị Hệ thống và các Nguyên lý",
    "Chương 2 Con người và các Khái niệm Đo lường Rủi ro",
    "Chương 21 Phần mềm Lạ và các cuộc Thử nghiệm Ứng dụng",
]

_LINES = [
    # line 1: ToC entry (letter-spaced, leader + page number) — not a start
    "Chương 1              N ề n t ả n g Q u ả n t r ị H ệ t h ố n g v à "
    "c á c N g u y ê n l ý ---------- 99",
    "",
    "98 | P a g e",
    "        Tên Sách Mẫu – Running Header",
    # line 5: chapter 1 body heading, wrapped
    "C h ư ơn g 1       N ề n t ả n g Q u ả n t r ị H ệ t h ốn g v à",
    "                   c á c Ng u yê n lý",
    "",
    "CÁC CHỦ ĐỀ TRONG CHƯƠNG NÀY:",
    "body of chapter one",
    "162 | P a g e",
    # line 11: chapter 2 body heading, wrapped
    "C h ư ơn g 2         C o n n g ư ời v à c á c K h á i n i ệ m Đ o",
    "                     lường Rủi ro",
    "",
    "body of chapter two",
    "1560 | P a g e",
    # line 16: chapter 21 — even the number is letter-spaced ("2 1")
    "C h ư ơn g 2 1       Phần mềm Lạ và các cuộc Thử nghiệm",
    "                     Ứng dụng",
    "",
    "body of chapter twenty-one",
]


def test_letter_spaced_wrapped_outline_headings_are_found():
    ranges = chapter_line_ranges("\n".join(_LINES), _TITLES)
    starts = {entry["title"]: entry["start_line"] for entry in ranges}
    # 1-based line numbers of the body headings, not the ToC line (1)
    assert starts == {_TITLES[0]: 5, _TITLES[1]: 11, _TITLES[2]: 16}


def test_letter_spaced_chapter_number_does_not_match_shorter_number():
    # "Chương 2 <ch21 title>" must not claim the "C h ư ơn g 2 1" heading.
    only_two = ["Chương 2 Phần mềm Lạ và các cuộc Thử nghiệm Ứng dụng"]
    assert chapter_line_ranges("\n".join(_LINES), only_two) == []
