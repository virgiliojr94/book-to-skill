---
name: factory-verify
description: Independently verify a factory pull request, including fail-closed gates, negative test proof, scope, and load-bearing review.
---

# Factory PR verification for Codex

Read `docs/factory/CONTRACT.md`, `docs/factory/CHARTER.md`, and then the canonical workflow
in `.claude/skills/factory-verify/SKILL.md`. Use a fresh subagent for any critic pass and the
shared `.factory/scripts/prove-test.sh` procedure for negative test proof.
