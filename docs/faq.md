---
description: "Answers on book-to-skill: why a skill beats dumping a book into context, how it compares to RAG and 1M-token windows, copyright, accuracy, and supported formats."
seo_title: "book-to-skill FAQ - Skills vs Context Dumps, RAG, Copyright"
---

## ❓ FAQ

**"Can't I just dump the PDF/EPUB into my Claude project context?"**

You can — but every conversation will burn that token budget upfront. A 400-page book is ~200K tokens. With a skill, only the chapters relevant to your question load — typically a SKILL.md core (~4K) plus the one chapter you asked about (~1K). The rest stays on disk until you need it.

The economics are amortization, not size. Pasting the book pays the full token bill **on every turn of every session, forever**. book-to-skill pays the extraction cost **once** and every future conversation loads only the slice it needs. The bigger your context window, the more this matters — a large window makes the dump *possible*, not *cheap*.

More importantly: raw text injection is retrieval. A skill is reasoning. When you load a chapter file, Claude isn't searching for keyword matches — it's working with pre-extracted named frameworks, principles, and mental models structured for application, not for reading.

---

**"Claude has a 1M-token context window now — can't I just keep the whole book loaded?"**

A bigger window changes what *fits*, not what's *smart*. Three reasons it isn't a substitute:

- **You pay per token, per call.** A 1M window doesn't make those tokens free — it makes a large, recurring bill possible. The skill loads kilobytes, not megabytes.
- **Recall degrades with fill.** Models lose precision retrieving a specific fact buried in a near-full context ("lost in the middle"). A 1K curated chapter beats 200K of raw prose for answering one question.
- **Window ≠ structure.** A full book in context is still raw text the model must re-parse every turn. The skill ships pre-extracted frameworks — reasoning, not retrieval.

Use the big window for what it's good at: a one-off pass over material you'll never need again. Use a skill for knowledge you'll reach for repeatedly.

---

**"Isn't this just RAG?"**

RAG works at query time: chunk the book → embed everything → find similar vectors → inject into prompt. It's optimized for "find me the part that talks about X."

book-to-skill works at compile time: one deep analysis run extracts the author's actual frameworks, names them, describes when to use each, captures the anti-patterns. The output is structure the author spent years building — not a similarity search over their sentences.

RAG answers: *"here are chunks close to your query."*  
A skill answers: *"here are the 12 frameworks this author built, ready to reason with."*

Pick by shape of the job:

- **Wide and shallow** — a library of dozens of books, "find the part that mentions X" → a RAG tool (e.g. CandleKeep) wins.
- **Narrow and deep** — one book or a tight cluster of related sources, frameworks you apply while you work → book-to-skill wins.

They're complementary, not competing: RAG indexes a shelf, book-to-skill masters a spine.

---

**"Popular books are already in Claude's training data. Why bother?"**

For widely-known books (Clean Code, DDIA, Pragmatic Programmer), Claude has general knowledge — but it's compressed, averaged across the entire internet's discussion of the book, and may hallucinate specific quotes or chapter locations.

book-to-skill works from your actual copy. Every framework name, every anti-pattern list, every chapter number is grounded in the text you provided. No training data drift, no hallucinated chapter titles.

It also shines for books Claude doesn't know at all: niche technical references, internal company documentation, recent publications, translated works.

---

**"NotebookLM handles multiple books better."**

Absolutely true — if your workflow is "I have 80 separate books and I want to search across all of them," NotebookLM is the right tool.

book-to-skill is built for a different job: you want to go deep on a specific topic or library, having multiple related documents (papers, chapters, notes) folded into a single unified skill, and even updating it over time as new material arrives! This integrates your customized knowledge base right into your coding or writing workflow, rather than in a separate browser tab.

---


---

[← Back to the README](../README.md)
