import pytest
from book_to_skill.chapter_detector import _chapter_number, detect_structure

def test_chapter_number_arabic():
    assert _chapter_number("Chapter 5") == 5
    assert _chapter_number("Capítulo 08: Instalação") == 8
    assert _chapter_number("Ch. 3") == 3
    # Prose/false positives
    assert _chapter_number("Chapter 5 is about something") is None

def test_chapter_number_roman():
    assert _chapter_number("I: Loomings") == 1
    assert _chapter_number("II. The Carpet-Bag") == 2
    assert _chapter_number("IV. Introduction") == 4
    # Non-canonical or prose
    assert _chapter_number("IIII. Invalid") is None
    assert _chapter_number("V is a letter") is None

def test_chapter_number_chinese():
    assert _chapter_number("第五章 安装") == 5
    assert _chapter_number("## 第一讲 概述") == 1
    assert _chapter_number("第十二节") == 12

def test_detect_structure():
    sample = """
    Table of Contents
    
    Chapter 1: Intro
    Some text.
    
    Chapter 2: Setup
    More text.
    """
    res = detect_structure(sample)
    assert res["chapters_detected"] == 2
    assert res["has_toc"] is True
    assert "Chapter 1: Intro" in res["chapter_headings_sample"]

