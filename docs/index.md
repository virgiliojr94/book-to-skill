---
hide:
  - navigation
  - toc
---

# book-to-skill

<p style="font-size: 1.25rem; max-width: 42rem;">
Turn any book or document into a structured, on-demand agent skill — named frameworks, decision rules, and anti-patterns. <strong>Structure, not a summary.</strong>
</p>

[Get started](guide.md){ .md-button .md-button--primary }
[Skill reference](skill-reference.md){ .md-button }
[GitHub](https://github.com/virgiliojr94/book-to-skill){ .md-button }

---

## Why book-to-skill

<div class="grid cards" markdown>

-   :material-file-document-multiple:{ .lg .middle } __Multi-format__

    ---

    PDF, EPUB, DOCX, HTML, Markdown, RTF, MOBI/AZW (via Calibre). Extraction runs
    locally with graceful stdlib fallbacks — no upload, no lock-in.

-   :material-brain:{ .lg .middle } __Structure, not summaries__

    ---

    Named frameworks, mental models, decision rules, and anti-patterns — the
    author's toolkit, captured with their exact terms, not a book report.

-   :material-flash:{ .lg .middle } __On-demand chapters__

    ---

    Per-chapter files load only when the topic is relevant, so a 200-page book
    costs tokens proportional to the question, not the page count.

-   :material-robot-happy:{ .lg .middle } __Multi-agent__

    ---

    One `SKILL.md` runs on Grok Build, Claude Code, GitHub Copilot CLI, and Amp
    through the open Agent Skills standard.

</div>

## Install

**As an agent skill** (gives you the `/book-to-skill` command in Grok Build,
Claude Code, Copilot CLI, or Amp):

```bash
# Choose the destination for your host:
# Grok Build
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.grok/skills/book-to-skill
# Claude Code
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
# GitHub Copilot CLI
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.copilot/skills/book-to-skill
# Grok Build, Copilot CLI, or Amp (shared path)
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.agents/skills/book-to-skill

# then, in your agent session:
/book-to-skill /path/to/book.pdf [skill-name]
```

**As a standalone CLI** (just the text extractor, optional):

```bash
pip install "book-to-skill[pdf,epub,docx]"
book-to-skill /path/to/book.pdf --mode text
```

## Learn more

<div class="grid cards" markdown>

-   :material-sitemap:{ .lg .middle } __[Architecture](ARCHITECTURE.md)__

    ---

    How the deterministic extractor and the spec-driven generator fit together.

-   :material-speedometer:{ .lg .middle } __[Performance](PERFORMANCE.md)__

    ---

    The measured Discovery Loop Tax and real per-conversion token cost.

-   :material-book-open-page-variant:{ .lg .middle } __[Skill Reference](skill-reference.md)__

    ---

    The full `SKILL.md` spec: every step, depth budget, and quality rule.

-   :material-heart:{ .lg .middle } __[Sponsor](https://github.com/sponsors/virgiliojr94)__

    ---

    book-to-skill is free and MIT. Sponsoring funds reviews, releases, and fixes.

</div>
