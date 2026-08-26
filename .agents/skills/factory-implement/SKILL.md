---
name: factory-implement
description: Claim and implement one ready GitHub issue, run fail-closed gates, obtain independent verification, and open a draft pull request.
---

# Factory implementation for Codex

Read `docs/factory/CONTRACT.md`, `docs/factory/CHARTER.md`, and then the canonical workflow
in `.claude/skills/factory-implement/SKILL.md`. Use Codex's subagent mechanism for the fresh
verifier context. If an independent context is unavailable, stop before opening a non-draft
pull request.
