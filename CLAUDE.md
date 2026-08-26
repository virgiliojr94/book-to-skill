@AGENTS.md

# Claude Code

Use `AGENTS.md` as the canonical repository instruction file. Do not duplicate repository-wide rules here.

## Project commands

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install pytest ruff bandit mkdocs-material mkdocs-redirects
python3 scripts/extract.py --check
ruff check --select E9,F --target-version py310 book_to_skill/ scripts/ tests/ tools/
pytest tests/ -q
python3 tools/validate_skill.py SKILL.md
mkdocs build
./.claude/scripts/gates.sh full   # the factory's deterministic verdict
```

## Project conventions

Python 3.9+ package in `book_to_skill/`; tests live in `tests/` and run with pytest.
Keep extraction local, preserve the no-raw-book-text and output-path security rules, and
add focused tests for behavior changes. Optional extractors must remain optional.

MiP-specific governance and approval rules are defined in `AGENTS.md` and remain
authoritative. Factory governs the bounded engineering work loop beneath those controls.

---

# Factory rules

This repository runs a software factory. Read `docs/factory/CONTRACT.md`, then
`docs/factory/CHARTER.md`, before acting. The contract is shared with Codex through
`AGENTS.md`; it is the source of truth for queue semantics and non-negotiable rules.
For first-time setup and the local dry run, follow `docs/factory/README.md`.

## Read first

The live queue is GitHub issue labels plus `factory-handoff:v1` comments.
`docs/factory/QUEUE.md` is a snapshot for humans and audit, so an unmerged snapshot must
never be used as the handoff between routines.

## Non-negotiable

1. **Never merge.** GitHub branch protection is the enforcement boundary; the local hook is
   a second layer.
2. **Never edit factory policy** unless the human explicitly asks in this session. Protected
   paths are listed in the charter.
3. **Never modify an existing test in an unattended run.** An interactive change needs
   explicit human approval and a human read. A new test file may be added under the charter's
   test-file exception.
4. **Gates fail closed.** Quote the `FACTORY_GATES:` line verbatim. `RED`,
   `MISCONFIGURED`, and required skips all block progress.
5. **Verification uses a fresh context.** Delegate to `factory-verifier`.
6. **Claim one live issue per run.** Win the deterministic remote-branch claim described in
   the contract, then replace `factory:ready-to-implement` with `factory:in-progress`.
7. **Report-only acceptance writes nothing.** Do not apply labels, edit comments, write
   snapshots or run records, open PRs, push branches, or enable triggers during a report-only
   acceptance run.

## Stopping conditions

Stop and hand back to a human when any of these is true:

- gates went red twice on the same item
- the work turns out to touch a `LOAD_BEARING` path outside the charter's new-test-file exception
- the diff would exceed the charter's line limit
- the item is still ambiguous after one clarification attempt
- the review queue is already at the charter's limit

The last one is the important one and the easiest to ignore. The constraint on this factory
is not how many agents can run in parallel. It is how many decisions are pending a human's
judgment at once. When that queue is full, producing more is not progress.

## State lives in files, not conversations

Write one immutable record under `docs/factory/runs/` using its documented format. Update
GitHub labels for operational state only during an explicitly authorized live workflow.
Report-only acceptance leaves the repository and GitHub state unchanged.

## Writing for the next reader

Commit messages and PR bodies are written for someone who was not in this session and
cannot ask you what you were thinking. On a `client-production` repo, assume that reader is
not the author and the time is six months from now.
