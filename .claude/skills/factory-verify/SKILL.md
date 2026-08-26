---
name: factory-verify
description: Verify an open factory PR before human review - re-runs gates, checks the test proves the fix, checks scope and test tampering. Use when reviewing a factory PR, running the PR review routine, or asked to independently check a change.
---

# Factory verify

Use this when a PR already exists and you are the check standing between it and a human.
For verification during implementation, the `factory-verifier` subagent is the right tool;
this skill is the PR-level version and can be driven by a GitHub-triggered routine.

## Procedure

1. Read `docs/factory/CONTRACT.md`, then `docs/factory/CHARTER.md` for the tier,
   load-bearing globs, and definition of done.
2. Check out the PR branch.
3. Run the required gate level yourself. Do not trust the `FACTORY_GATES` line in the PR
   body; produce your own and compare. A mismatch is the finding.
4. Run the checks the deterministic gates cannot make:
   - Does the test fail without the implementation? Start from a clean committed branch and
     run `./.factory/scripts/prove-test.sh <base-ref> --test-path <test-path> -- <focused-test-command>`.
     Do not use `git stash` or an ad hoc destructive revert.
   - Were pre-existing test files modified? Any change there needs an explicit, argued
     justification in the PR body.
   - Does the diff stay inside the declared scope?
   - Is `done_when` literally true?
5. For anything touching a load-bearing path, or any PR where the diff looks suspiciously
   clean, additionally run the `factory-critic` subagent and include its output.

## Reporting

Post one PR comment. Structure it so a human reads the verdict first and the detail only if
they need it.

```markdown
### Factory verification

**Verdict:** accepted | accepted-with-reservations | rejected
**Human read required:** yes (<reason>) | no

<the FACTORY_GATES line, verbatim>

| Check | Result |
|---|---|
| Gates reproduce PR claim | yes / no |
| Test fails without fix | yes / no / could-not-determine |
| Pre-existing tests untouched | yes / no |
| Scope within declared files | yes / no |
| done_when literally true | yes / no |

**Must fix**
1. ...

**Critic** (load-bearing changes only)
<factory-critic output>
```

Apply the label `factory:verified` or `factory:rejected`.

Write one unique `verify` run record under `docs/factory/runs/`; do not append to
`STATE.md`.

## What this is for, and what it is not

This routes a human's attention. It is not an approval and it never merges.

The value is allocation: a human reads the flagged PRs closely and gives the rest a
confirming glance, instead of spreading the same attention evenly over everything. That
reallocation is the whole point, and it only works if the flags are trustworthy, which is
why the standing bias is to reject when uncertain.

## Standing bias

Reject when uncertain. A false accept is worse than no verification, because it spends a
human's trust that was never earned. They will read the next one less carefully because
this one said it was fine.
