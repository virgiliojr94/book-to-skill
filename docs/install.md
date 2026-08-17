---
description: "Install book-to-skill as an agent skill for Claude Code, GitHub Copilot CLI, Amp and Codex, or as a standalone pip CLI. Every host path and optional extractor covered."
seo_title: "Install book-to-skill - Claude Code, Copilot CLI, Amp, or pip"
---

## 📥 Install

> **Two ways to use it, do not confuse them:**
> - **As an agent skill** (the `/book-to-skill` command in Claude Code, Copilot CLI, Amp, or Codex) → **`git clone` into your skills folder** (below). This is what gives you the slash command and the full convert-a-book flow.
> - **As a standalone CLI** (just the text extractor) → `pip install book-to-skill`, then `book-to-skill --help`. This does **not** register the agent skill; it only installs the extraction engine. See [the CLI section](#standalone-cli-pip).

The skill follows the open [Agent Skills](https://github.com/agentskills/agentskills) standard, so a single install works for any compatible host.

**One command, any host** — the [`skills` CLI](https://skills.sh) resolves the repo, detects the root `SKILL.md`, and installs the complete skill (including `scripts/extract.py` and `tools/`) into the skills folder of every host you select:

```bash
npx skills add virgiliojr94/book-to-skill
```

Prefer a manual install? Every per-host `git clone` path below works exactly the same.

**GitHub Copilot CLI** (personal skill):

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.copilot/skills/book-to-skill
# then, in a `copilot` session:
/skills reload
/skills info book-to-skill
```

Or the cross-agent path that Copilot CLI, Amp and Codex all discover:

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.agents/skills/book-to-skill
```

**OpenAI Codex** reads `~/.agents/skills` and follows symlinks, so the clone above is all it needs. A local checkout works too, linked in rather than copied:

```bash
ln -s /path/to/book-to-skill ~/.agents/skills/book-to-skill
```

**Claude Code**:

Copy this into your Claude Code session:

```
Install book-to-skill: https://raw.githubusercontent.com/virgiliojr94/book-to-skill/master/SKILL.md
```

Or manually using standard `git clone` (ensures modular engine files are fetched correctly):

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
```

Then in any agent session:

```bash
/book-to-skill ~/path/to/your-book.pdf
# or
/book-to-skill ~/path/to/your-book.epub
```

### Standalone CLI (pip)

`pip install book-to-skill` is a **separate, optional** path. It installs only the
text-extraction engine as a CLI, for scripting or to grab the optional extractors;
it does **not** register the `/book-to-skill` agent skill (use the `git clone` above
for that).

```bash
pip install "book-to-skill[pdf,epub,docx]"   # engine + optional extractors
book-to-skill ~/path/to/book.pdf --mode text  # or: python -m book_to_skill ...
book-to-skill --check                          # report which extractors are installed
```

---


---

[← Back to the README](../README.md)
