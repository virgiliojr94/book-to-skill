---
description: "Every way to run /book-to-skill: a single file, a folder, a glob, or a list of paths, with extraction modes, skill naming, and worked command examples."
seo_title: "Usage - Convert a Book, Folder, or Glob into an Agent Skill"
---

## 🚀 Usage

```
/book-to-skill <path-to-document-folder-or-glob>... [skill-name-slug]
```

Supported document formats: PDF, EPUB, DOCX, TXT, Markdown, reStructuredText, AsciiDoc, HTML, RTF, MOBI/AZW/AZW3.

**Examples:**

```bash
# Process several files together into a unified skill
/book-to-skill ~/papers/paper1.pdf ~/notes/export.txt unified-research

# Process all supported files in a folder together
/book-to-skill ~/workspace/project-docs/ project-knowledge

# Process files matching a glob pattern
/book-to-skill "~/books/*.epub" my-library

# Update/fold new material into an existing skill folder
/book-to-skill ~/articles/new-paper.pdf ~/.claude/skills/project-knowledge
```

After the skill is created, use it like any other agent skill:

```bash
/designing-data-intensive-apps                  # load core mental models
/designing-data-intensive-apps replication      # find and explain a topic
/designing-data-intensive-apps ch05             # dive into chapter 5
/designing-data-intensive-apps "what chapters do you have?"
```

In GitHub Copilot CLI you may need to run `/skills reload` after the file is written so the new skill appears in `/skills list`. Claude Code and Amp pick it up on the next session.

---

## 💬 What people do with it

A DevEx book became a survey applied to 300+ engineers. A scanned PDF that stalled a run became [#130](https://github.com/virgiliojr94/book-to-skill/pull/130), the early-abort fix — reported by someone who does not write software.

Both accounts, and how to add yours, are in [book-to-skill-use-cases](https://github.com/virgiliojr94/book-to-skill-use-cases): your write-up as a Gist on your own account, one line in the index, no template and no CI. Bring the numbers from your run or what came of it — and say where it fell short.

---

## 📤 Publish your generated skill (optional)

After a conversion, the converter offers to push the skill to GitHub as its own repository. Visibility is asked as its own question and the `gh repo create` command defaults to **`--private`**; a public repo is created only when your answer is the bare word `public`. A sentence about the source's licence is not a visibility answer - "it's public domain" describes the book, not the repository, and still gets you a private repo. Chapter files are synthesized from the source material, and skills generated from third-party copyrighted books must stay private (see [Copyright & fair use](../README.md#%EF%B8%8F-copyright--fair-use)). A published skill installs on any Agent Skills host in one command:

```bash
npx skills add https://github.com/<you>/<your-book-slug> --skill <your-book-slug>
```

Requires the [`gh` CLI](https://cli.github.com), authenticated. The generated repo ships with a README, and the skill folder becomes the git working copy, so later fold-in updates can push to the same remote.

---

[← Back to the README](../README.md)
