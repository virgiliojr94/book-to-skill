---
description: "Install book-to-skill as an agent skill for Claude Code, GitHub Copilot CLI, Amp, Codex, Hermes Agent and OpenCode, or as a standalone pip CLI. Every host path and optional extractor covered."
seo_title: "Install book-to-skill - Claude Code, Copilot CLI, Amp, Hermes, OpenCode, or pip"
---

## 📥 Install

> **Two ways to use it, do not confuse them:**
> - **As an agent skill** (the `/book-to-skill` command in Claude Code, Copilot CLI, Amp, Codex, Hermes Agent, or OpenCode) → **`git clone` into your skills folder** (below). This is what gives you the slash command and the full convert-a-book flow.
> - **As a standalone CLI** (just the text extractor) → `pip install` it from the repository, then `book-to-skill --help`. This does **not** register the agent skill; it only installs the extraction engine. See [the CLI section](#standalone-cli-pip).

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

**OpenCode**: it scans the shared cross-agent root natively, so the clone above is all it needs:

```bash
# Cross-agent root (shared with Copilot CLI, Amp and Codex) — recommended:
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.agents/skills/book-to-skill
# Or OpenCode's own managed root, if you'd rather keep it separate:
# git clone https://github.com/virgiliojr94/book-to-skill.git ~/.config/opencode/skills/book-to-skill
```

OpenCode discovers skills from `~/.agents/skills`, `~/.config/opencode/skills` and
`~/.claude/skills` (global) and `.opencode/skills`, `.agents/skills`,
`.claude/skills` (project-local, walking up from your working directory to the
git worktree). Discovery is automatic — no trust step required. Start a new
OpenCode session if the skill does not appear immediately.

**Hermes Agent**:

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git \
  "${HERMES_HOME:-$HOME/.hermes}/skills/productivity/book-to-skill"
```

`HERMES_HOME` is profile-aware and defaults to `~/.hermes`. The converter can
live under another existing Hermes category if preferred. Start a new Hermes
session, then invoke `/book-to-skill` or ask Hermes to use the `book-to-skill`
skill. Generated book skills should go under the category that matches their
subject rather than automatically reusing `productivity`.

For a project-local installation, use `.hermes/skills/<category>/book-to-skill`
and explicitly trust the project before starting a new session:

```bash
hermes skills trust /path/to/project
hermes skills list
```

Hermes does not load project-local skills from `.hermes/skills/` or
`.agents/skills/` until that project has been trusted.

**Claude Code**:

Copy this into your Claude Code session:

```
Install book-to-skill: https://raw.githubusercontent.com/virgiliojr94/book-to-skill/master/SKILL.md
```

Or manually using standard `git clone` (ensures modular engine files are fetched correctly):

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
# Project-local (share with team via git):
# git clone https://github.com/virgiliojr94/book-to-skill.git .claude/skills/book-to-skill
```

> **Generated book skills — where do they go?** By default the converter uses the established **Personal (global)** root (`~/.agents/skills/<slug>/` for most hosts). **Project-local** output (`.claude/skills/<slug>/`, `.agents/skills/<slug>/`, or `.github/skills/<slug>/`) is an explicit choice for project-specific, git-shareable skills and may require host approval to write inside the project. Set `BOOK_TO_SKILL_SCOPE=project` or `personal` to make the scope explicit for automation; the converter does not ask a mandatory scope question merely because both scopes are available.

Scope-selection check:

```text
Before: no scope request or BOOK_TO_SKILL_SCOPE → personal default (~/.agents/skills)
After:  BOOK_TO_SKILL_SCOPE=project or an explicit project-local request → project-local host root
```

Then in any agent session:

```bash
/book-to-skill ~/path/to/your-book.pdf
# or
/book-to-skill ~/path/to/your-book.epub
```

### Standalone CLI (pip)

Installing the CLI with `pip` is a **separate, optional** path. It installs only the
text-extraction engine as a CLI, for scripting or to grab the optional extractors;
it does **not** register the `/book-to-skill` agent skill (use the `git clone` above
for that).

`book-to-skill` is not on PyPI yet, so `pip` takes the package straight from the
repository:

```bash
pip install "book-to-skill[pdf,epub,docx] @ git+https://github.com/virgiliojr94/book-to-skill.git"
book-to-skill ~/path/to/book.pdf --mode text  # or: python -m book_to_skill ...
book-to-skill --check                          # report which extractors are installed
```

> **`[html]` is heavier than the others.** It pulls in `trafilatura`, which brings a full
> HTML-processing stack (lxml, a date parser, a timezone database, a URL classifier — 17
> packages total) to do real main-content/boilerplate detection instead of just stripping
> `<script>`/`<style>`. Worth knowing before installing on a constrained machine — the
> `bs4` fallback (no `[html]` extra needed) still works, just without boilerplate removal.

---


---

[← Back to the README](../README.md)
