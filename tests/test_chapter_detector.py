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
    assert len(res["ast"]) == 3
    assert res["ast"][0]["title"] == "Prefácio / Introdução"
    assert res["ast"][1]["title"] == "Chapter 1: Intro"


def test_detect_structure_ast_nested():
    sample = """# Part 1
Introductory notes.

## Chapter 1: Foundations
Core knowledge.

### Section 1.1
Detailing the core.

# Part 2
Concluding notes.
"""
    res = detect_structure(sample)
    ast = res["ast"]
    
    # 2 root nodes: Part 1 and Part 2
    assert len(ast) == 2
    assert ast[0]["title"] == "Part 1"
    assert ast[0]["level"] == 1
    assert len(ast[0]["children"]) == 1
    
    ch1 = ast[0]["children"][0]
    assert ch1["title"] == "Chapter 1: Foundations"
    assert ch1["level"] == 2
    assert len(ch1["children"]) == 1
    
    sec11 = ch1["children"][0]
    assert sec11["title"] == "Section 1.1"
    assert sec11["level"] == 3
    
    assert ast[1]["title"] == "Part 2"
    assert ast[1]["level"] == 1
    
    # Verify slices
    assert sample[sec11["start_char"]:sec11["end_char"]].startswith("### Section 1.1")
    assert sample[ast[1]["start_char"]:ast[1]["end_char"]].strip() == "# Part 2\nConcluding notes."


def test_detect_structure_ast_no_headers():
    sample = "Este é um texto simples sem nenhum cabeçalho."
    res = detect_structure(sample)
    ast = res["ast"]
    assert len(ast) == 1
    assert ast[0]["title"] == "Documento Completo"
    assert ast[0]["start_char"] == 0
    assert ast[0]["end_char"] == len(sample)


def test_detect_structure_ast_with_preface():
    sample = """Prefácio muito longo e importante contendo notas dos autores.
E agradecimentos.

# Chapter 1: Start
Text body.
"""
    res = detect_structure(sample)
    ast = res["ast"]
    assert len(ast) == 2
    assert ast[0]["title"] == "Prefácio / Introdução"
    assert ast[0]["start_char"] == 0
    assert ast[0]["end_char"] == sample.find("# Chapter 1: Start")
    
    assert ast[1]["title"] == "Chapter 1: Start"


def test_detect_structure_ast_flat():
    sample = """Chapter 1: Start
Text body of chapter 1.

Chapter 2: Continuation
Text body of chapter 2.

Chapter 3: End
Text body of chapter 3.
"""
    res = detect_structure(sample)
    ast = res["ast"]
    
    # 3 root nodes, no children
    assert len(ast) == 3
    assert ast[0]["title"] == "Chapter 1: Start"
    assert ast[0]["level"] == 1
    assert len(ast[0]["children"]) == 0
    assert ast[0]["start_char"] == 0
    assert ast[0]["end_char"] == sample.find("Chapter 2: Continuation")
    
    assert ast[1]["title"] == "Chapter 2: Continuation"
    assert ast[1]["level"] == 1
    assert len(ast[1]["children"]) == 0
    assert ast[1]["start_char"] == sample.find("Chapter 2: Continuation")
    assert ast[1]["end_char"] == sample.find("Chapter 3: End")
    
    assert ast[2]["title"] == "Chapter 3: End"
    assert ast[2]["level"] == 1
    assert len(ast[2]["children"]) == 0
    assert ast[2]["start_char"] == sample.find("Chapter 3: End")
    assert ast[2]["end_char"] == len(sample)



