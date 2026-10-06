"""Keep translated destination policy and Russian headings from regressing."""

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]

POLICY_TERMS = {
    "README.ru.md": ("символьную ссылку", "проверяет её чтением"),
    "README.zh-CN.md": ("符号链接", "回读验证"),
}


@pytest.mark.parametrize(("path", "translated_terms"), POLICY_TERMS.items())
def test_translated_destination_policy_is_pinned_and_complete(path, translated_terms):
    text = (ROOT / path).read_text(encoding="utf-8")

    assert re.search(
        r"<!-- translation-meta: source=README\.md@[0-9a-f]{40} "
        r"date=\d{4}-\d{2}-\d{2} scope=destination-policy(?: [^>]*)? -->",
        text,
    )
    required_terms = (
        "~/.agents/skills/<slug>/",
        "~/.claude/skills/<slug>/",
        "OPENCLAW_STATE_DIR",
        "HERMES_HOME",
        *translated_terms,
    )
    assert all(term in text for term in required_terms)


def test_russian_section_headings_are_localized():
    text = (ROOT / "README.ru.md").read_text(encoding="utf-8")
    headings = {line for line in text.splitlines() if line.startswith("## ")}

    assert {
        "## 🧾 Цена цикла поиска",
        "## ⚙️ Как это работает",
        "## 🚀 Использование",
        "## 📥 Установка",
        "## ❓ Частые вопросы",
        "## ⚖️ Авторское право и добросовестное использование",
        "## 💖 Спонсоры",
        "## Лицензия",
        "## История звёзд",
    } <= headings
