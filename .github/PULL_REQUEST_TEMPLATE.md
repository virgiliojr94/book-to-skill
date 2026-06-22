<!--
PR title: use Conventional Commits, e.g. `fix(extractor): scan full text`, `feat(cli): ...`.
Fill EVERY section marked (Required). Sections marked (Optional) can be deleted if not applicable.
A PR that leaves Required sections empty or unchecked will be asked to complete them before review.
-->

## Summary (Required)
<!-- In 1-3 sentences and plain language: what does this PR do? Someone skimming
     should understand the change without reading the diff. -->


## Type of change (Required)
<!-- Mark all that apply with [x]. -->
- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ Feature (non-breaking change that adds capability)
- [ ] ⚡ Performance (faster / cheaper, no behavior change)
- [ ] ♻️ Refactor (no behavior change)
- [ ] 📝 Docs only
- [ ] 🔒 Security
- [ ] 🧹 Chore / CI / tooling
- [ ] 💥 Breaking change (changes existing behavior or a public interface)

## What it does (Required)
<!-- Be specific. Use the lines that apply, delete the rest. -->
- **Fixes:** <!-- the exact wrong behavior, and the root cause -->
- **Improves:** <!-- what gets better, and by how much (numbers, not adjectives) -->
- **Adds:** <!-- the new capability and who it is for -->

## Motivation & context (Required)
<!-- Why is this needed? What problem or use case drives it? -->
Closes #<!-- issue number, or "n/a" with a one-line reason if there is no issue -->

## How it works (Required for anything non-trivial)
<!-- The approach: key decision(s), why this way, any alternative you rejected.
     For a one-line fix, "see diff" is fine. -->


## Evidence (Required)
<!-- Proof, not claims. This project's rule is "measure, don't assert". -->
- **Tests:** <!-- which tests you added/changed and what they assert -->
- **Before / after:** <!-- terminal output, repro of the bug, or measured numbers.
     For performance: a `tools/discovery_tax.py` number or a timed before/after.
     For a bug fix: the failing input and the now-correct output. -->

```
<!-- paste the before/after terminal output here -->
```

## Screenshots / output (Required if behavior or output changes — Optional for pure internal refactor)
<!-- Drag in an image: the bug vs the fix, the generated skill, the dashboard, etc.
     A picture of broken-vs-fixed is the fastest way to get a PR reviewed.
     Delete this section only for invisible internals. -->


## Checklist (Required — all must be checked)
- [ ] One focused change (one feature/fix per PR; not a stack of unrelated work)
- [ ] Branch is rebased on the latest `master` and has no merge conflicts
- [ ] Tests added/updated for behavior changes
- [ ] `pytest -q` is green on a clean checkout
- [ ] `ruff check .` is clean
- [ ] `python3 tools/validate_skill.py SKILL.md` passes (if `SKILL.md` changed)
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`
- [ ] No raw book text shipped; no net `SKILL.md` bloat without justification

## Breaking changes & back-compat (Optional)
<!-- What breaks, who is affected, and the migration path. Delete if none. -->

## Notes for reviewers (Optional)
<!-- Anything that helps review: areas you are unsure about, follow-ups you left
     out on purpose, things explicitly out of scope. -->
