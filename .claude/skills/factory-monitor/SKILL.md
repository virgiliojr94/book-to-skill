---
name: factory-monitor
description: Scheduled health sweep that closes the factory loop - reads CI failures, recent commits, dependency and security advisories, and live queue labels, then files issues and writes an immutable run record. Use for the nightly or weekly monitor routine.
---

# Factory monitor

This is the stage that closes the loop. Without it a factory only processes work a human
remembered to file, which means the backlog reflects attention rather than reality.

**You file issues. You do not fix anything.** Mixing detection and repair in one run means
a bad detection becomes a bad commit before anyone sees it.

Read `docs/factory/CONTRACT.md` and `docs/factory/CHARTER.md` first.

## Sweep

Run each of these. Where a check is not applicable to this repo, say so rather than
silently skipping it.

**1. CI failures.** Failed runs on the default branch since the last sweep. For each,
identify the failing job and whether it is a genuine regression or a flake. A test that
failed once and passed on rerun is a flake finding, not a bug finding, and it is worth
tracking separately because flakes are what erode trust in the gates.

**2. Gate health.** Run `./.claude/scripts/gates.sh deep` on the default branch. A gate
that is red on `main` means every downstream verdict this week was measured against a
broken baseline. This is the highest-priority finding the sweep can produce.

Treat `MISCONFIGURED` as a factory-blocking finding. Also report optional skips so a human
can decide whether they should become required.

**3. Dependencies and advisories.** New security advisories affecting direct dependencies.
Group by severity. Do not file an issue per transitive dependency; that is noise that
trains people to ignore the sweep.

**4. Queue staleness.** Query live GitHub labels and issue timestamps. Use `QUEUE.md` only
as supporting history:
   - `in-progress` with no new commit or run record for 2 hours → flag the deterministic
     claim branch for human recovery; do not delete or take it over automatically
   - `awaiting-review` for more than 7 days → the human review queue is the bottleneck,
     and per the charter's `STOP_IF` the factory should be throttling intake
   - `wait-to-implement` whose named blocker has since resolved → promote it
   - `needs-info` with an answer now in the issue comments → send back to triage

**5. Comprehension drift.** Files changed by the factory more than 5 times in the last 30
days with no corresponding update to their documentation or to `docs/factory/DECISIONS.md`.
These are the places where the code has moved and the written understanding has not, which
is where the next surprise comes from.

**6. Charter gaps.** Anything triage flagged as not covered by `CHARTER.md`. Collect them
into a single issue for a human decision rather than one issue each.

## Filing

For each genuine finding, file a GitHub issue with the `factory:monitor` label. Before
filing, search open issues for a duplicate; a monitor that refiles the same issue weekly
gets muted, and a muted monitor is worse than none.

Issue body:

```markdown
**Detected:** <date> by factory-monitor
**Category:** ci-failure | gate-health | advisory | queue-staleness | comprehension-drift | charter-gap
**Severity:** blocks-factory | high | medium | low

**What**
<one paragraph>

**Evidence**
<log excerpt, gate line, commit range - the actual artifact, not a description of it>

**Suggested disposition**
ready-to-implement | ready-to-spec | needs-info
```

Use `blocks-factory` only for red gates on the default branch or a full review queue. Those
two conditions mean the factory should stop producing, and the severity should say so.

## Report

Write one unique `monitor` run record under `docs/factory/runs/`:

- one line per finding with its issue link
- the current queue depth by disposition
- **the review-queue depth**, called out separately, because that is the number that
  actually constrains the factory
- what you checked and found clean, so the absence of findings is distinguishable from the
  absence of checking

That last point matters more than it looks. A silent monitor is ambiguous between "nothing
is wrong" and "the sweep did not run", and those need very different responses.

## What you never do

- Fix anything, including one-line fixes that look obviously safe
- File more than 10 issues in a run. If you found more, file the top 10 by severity and say
  how many you dropped. **Never silently truncate.**
- Reopen or comment on issues a human closed
