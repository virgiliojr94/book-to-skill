---
description: "Turn any book, PDF or EPUB into a structured agent skill for Claude Code, GitHub Copilot CLI and Amp. Named frameworks and decision rules, loaded on demand."
seo_title: "book-to-skill - Turn Any Book Into an AI Agent Skill"
hide:
  - navigation
  - toc
---

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "book-to-skill",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Linux, macOS, Windows",
  "description": "Converts books and documents (PDF, EPUB, DOCX, HTML, Markdown, RTF, MOBI/AZW) into structured, on-demand agent skills for Claude Code, GitHub Copilot CLI and Amp.",
  "url": "https://booktoskill.is-a.dev/",
  "codeRepository": "https://github.com/virgiliojr94/book-to-skill",
  "license": "https://opensource.org/licenses/MIT",
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "author": { "@type": "Person", "name": "virgiliojr94", "url": "https://github.com/virgiliojr94" }
}
</script>

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

    One `SKILL.md` runs on Claude Code, GitHub Copilot CLI, and Amp through the
    open Agent Skills standard.

</div>

## Install

**As an agent skill** (gives you the `/book-to-skill` command in Claude Code, Copilot CLI, Amp):

```bash
npx skills add virgiliojr94/book-to-skill
# or manually:
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
# then, in your agent session:
/book-to-skill /path/to/book.pdf [skill-name]
```

**As a standalone CLI** (just the text extractor, optional):

```bash
# not on PyPI yet — pip takes it from the repository
pip install "book-to-skill[pdf,epub,docx] @ git+https://github.com/virgiliojr94/book-to-skill.git"
book-to-skill /path/to/book.pdf --mode text
```

## Learn more

<div class="grid cards" markdown>

-   :material-sitemap:{ .lg .middle } __[Architecture](architecture.md)__

    ---

    How the deterministic extractor and the spec-driven generator fit together.

-   :material-speedometer:{ .lg .middle } __[Performance](performance.md)__

    ---

    The measured Discovery Loop Tax and real per-conversion token cost.

-   :material-book-open-page-variant:{ .lg .middle } __[Skill Reference](skill-reference.md)__

    ---

    The full `SKILL.md` spec: every step, depth budget, and quality rule.

-   :material-heart:{ .lg .middle } __[Sponsor](https://github.com/sponsors/virgiliojr94)__

    ---

    book-to-skill is free and MIT. Sponsoring funds reviews, releases, and fixes.

</div>
