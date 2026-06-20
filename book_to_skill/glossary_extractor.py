from __future__ import annotations

import re
from collections import Counter

# Common English and Portuguese stopwords to filter out keywords
STOPWORDS = {
    # English
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "in", "on", "at", "to", "for", "with", "by", 
    "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "from", 
    "up", "down", "out", "off", "over", "under", "again", "further", "once", "here", "there", "when", "where", 
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", 
    "not", "only", "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now", "this", 
    "that", "these", "those", "are", "was", "were", "been", "has", "have", "had", "does", "done", "from", "with",
    # Portuguese
    "o", "a", "os", "as", "de", "do", "da", "dos", "das", "em", "um", "uma", "uns", "umas", "no", "na", "nos", 
    "nas", "para", "por", "com", "como", "que", "se", "ou", "mas", "e", "é", "são", "este", "esta", "estes", 
    "estas", "esse", "essa", "esses", "essas", "aquele", "aquela", "aquilo", "seu", "sua", "seus", "suas", 
    "meu", "minha", "meus", "minhas", "ele", "ela", "eles", "elas", "nós", "vós", "dele", "dela", "deles", 
    "delas", "esteja", "estive", "estiver", "estou", "está", "estamos", "estão", "estava", "estavam", "estivemos", 
    "estiveram", "como", "uma", "mais", "para", "pelo", "pela", "pelos", "pelas", "seus", "suas", "todo", "toda"
}

# Regex definitions
ACRONYM_RE = re.compile(r"\b(?=[A-Z0-9]*[A-Z])[A-Z0-9]{2,6}\b")
BOLD_DEF_RE = re.compile(r"\*\*([A-Za-zÀ-ÖØ-öø-ÿ0-9_ -]+)\*\*\s*[:—\-]\s*([^.\n]+)")
VERB_DEF_RE = re.compile(
    r"\b([A-ZÀ-Ö][a-za-zÀ-ÖØ-öø-ÿ0-9_ -]{2,30})\b\s+(?:refere-se a|é definido como|significa|refers to|is defined as|is a|is an)\s+([^.\n]+)",
    re.IGNORECASE
)
CODE_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)\n(.*?)```", re.DOTALL)


def clean_term(term: str) -> str:
    """Normalize a term by stripping whitespace and extra punctuation."""
    return term.strip().strip("*:— -")


def clean_definition(definition: str) -> str:
    """Clean and normalize definition text."""
    return definition.strip().strip(".:— -") + "."


def extract_sentence_around(text: str, pos: int) -> str:
    """Extract the sentence enclosing the character offset `pos`."""
    # Find start of sentence (previous period, newline, or start of string)
    start = pos
    while start > 0 and text[start] not in (".", "\n", "?", "!"):
        start -= 1
    if start > 0:
        start += 1  # step after the period
        
    # Find end of sentence (next period, newline, or end of string)
    end = pos
    while end < len(text) and text[end] not in (".", "\n", "?", "!"):
        end += 1
        
    sentence = text[start:end].strip()
    # Normalize spacing
    sentence = re.sub(r"\s+", " ", sentence)
    if sentence and not sentence.endswith((".", "?", "!")):
        sentence += "."
    return sentence


def extract_glossary_data(text: str) -> dict:
    """Parse text and extract acronyms, pattern-based definitions, and statistical keywords."""
    terms_dict = {}

    # 1. Bold Definitions (**Term** — definition)
    for match in BOLD_DEF_RE.finditer(text):
        term = clean_term(match.group(1))
        definition = clean_definition(match.group(2))
        if len(term) > 1 and len(definition) > 5 and term.lower() not in STOPWORDS:
            terms_dict[term] = {
                "term": term,
                "definition": definition,
                "type": "pattern_bold",
                "frequency": 1
            }

    # 2. Verb-based Definitions (Term refers to / Termo é definido como)
    for match in VERB_DEF_RE.finditer(text):
        term = clean_term(match.group(1))
        definition = clean_definition(match.group(2))
        if len(term) > 1 and len(definition) > 5 and term.lower() not in STOPWORDS:
            # Only replace if not already found in bold patterns (bold patterns are usually cleaner)
            if term not in terms_dict:
                terms_dict[term] = {
                    "term": term,
                    "definition": definition,
                    "type": "pattern_verb",
                    "frequency": 1
                }

    # 3. Acronyms & Frequencies
    acronyms = ACRONYM_RE.findall(text)
    acronym_counts = Counter(acronyms)
    
    for acronym, freq in acronym_counts.items():
        if acronym.lower() in STOPWORDS:
            continue
        # Find first sentence containing this acronym to act as a placeholder definition
        first_pos = text.find(acronym)
        definition = "Term found in the text."
        if first_pos != -1:
            definition = extract_sentence_around(text, first_pos)
            
        if acronym in terms_dict:
            terms_dict[acronym]["frequency"] += freq
            if terms_dict[acronym]["type"] == "statistical":
                terms_dict[acronym]["type"] = "acronym"
        else:
            terms_dict[acronym] = {
                "term": acronym,
                "definition": definition,
                "type": "acronym",
                "frequency": freq
            }

    # 4. Statistical Keywords (Frequent words starting with Capital letters not at start of line)
    # Find all capitalized words in the text
    cap_words = re.findall(r"\b[A-ZÀ-Ö][a-zà-öø-ÿ]{2,15}\b", text)
    word_counts = Counter(cap_words)
    
    # Filter out stopwords and highly rare words
    filtered_keywords = [
        (word, freq) for word, freq in word_counts.items()
        if word.lower() not in STOPWORDS and freq >= 2 and word not in terms_dict
    ]
    # Take top 15 remaining keywords
    top_keywords = sorted(filtered_keywords, key=lambda x: x[1], reverse=True)[:15]
    
    for word, freq in top_keywords:
        first_pos = text.find(word)
        definition = "Keyword extracted from text."
        if first_pos != -1:
            definition = extract_sentence_around(text, first_pos)
            
        terms_dict[word] = {
            "term": word,
            "definition": definition,
            "type": "statistical",
            "frequency": freq
        }

    # Sort terms alphabetically
    sorted_terms = sorted(terms_dict.values(), key=lambda x: x["term"].lower())
    return {"terms": sorted_terms}


def extract_code_blocks(text: str) -> list[dict]:
    """Scan and return all code blocks in the text."""
    blocks = []
    for match in CODE_BLOCK_RE.finditer(text):
        lang = match.group(1).strip() or "plaintext"
        code = match.group(2).strip()
        if code:
            blocks.append({
                "language": lang,
                "code": code
            })
    return blocks


def generate_cheatsheet_markdown(text: str, glossary: dict, title: str) -> str:
    """Generate a clean cheatsheet markdown containing acronyms, definitions, and code blocks."""
    terms = glossary.get("terms", [])
    
    acronyms = [t for t in terms if t["type"] == "acronym"]
    definitions = [t for t in terms if t["type"] in ("pattern_bold", "pattern_verb", "statistical")]
    code_blocks = extract_code_blocks(text)
    
    md_lines = [
        f"# Cheatsheet: {title}",
        "",
        "Quick reference guide automatically extracted from the source documents.",
        ""
    ]
    
    if acronyms:
        md_lines.append("## Key Acronyms")
        for acr in acronyms:
            md_lines.append(f"- **{acr['term']}**: {acr['definition']} *(found {acr['frequency']} time(s))*")
        md_lines.append("")
        
    if definitions:
        md_lines.append("## Key Terms & Definitions")
        for defn in definitions:
            md_lines.append(f"- **{defn['term']}**: {defn['definition']}")
        md_lines.append("")
        
    if code_blocks:
        md_lines.append("## Code Snippets & Practical Examples")
        for idx, block in enumerate(code_blocks):
            md_lines.append(f"### Example {idx + 1} ({block['language']})")
            md_lines.append(f"```{block['language']}")
            md_lines.append(block['code'])
            md_lines.append("```")
            md_lines.append("")
            
    if not acronyms and not definitions and not code_blocks:
        md_lines.append("No structured terms, acronyms, or code blocks could be automatically extracted from this segment.")
        
    return "\n".join(md_lines)
