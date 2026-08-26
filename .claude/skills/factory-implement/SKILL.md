---
name: factory-implement
description: Claim one live GitHub queue item, implement it end to end, run fail-closed gates and independent verification, then open a draft PR. Use for one ready-to-implement issue or the implementation routine.
---

# Factory implementation

You implement **exactly one queue item per run**. Not two. If you finish early, stop.

Batching items is how a single wrong assumption becomes a wide diff nobody can review.

## Before writing any code

1. Read `docs/factory/CONTRACT.md`, then `docs/factory/CHARTER.md`.
2. Query GitHub for open issues labeled `factory:ready-to-implement`. The live label is
   authoritative; read the latest `factory-handoff:v1` comment for `done_when`, expected
   files, gate level, and confidence. `QUEUE.md` is only a snapshot. If the handoff is
   missing, duplicated, malformed, or inconsistent with the charter, move the issue to
   `factory:needs-info` and stop. If running locally without GitHub access, stop unless a
   human explicitly selects an item for an interactive run.
3. Select one item and win the deterministic remote-branch claim described below. Only
   after that push succeeds, replace `factory:ready-to-implement` with
   `factory:in-progress`. Re-read the issue after the write. If either step failed, stop.
4. Re-read `done_when`. This is your stopping condition. You are done when it is true and
   gates are green, not when the code looks finished.
5. Check the item against `LOAD_BEARING` yourself. Triage can be wrong. If the work turns
   out to touch a load-bearing path beyond a new test file allowed by the charter's test-file
   rule, **stop**, move the item to `ready-to-spec`, and record why. Do not proceed carefully;
   proceed not at all.

If the review queue is already at the charter limit, do not claim an item. Stop and record
the back-pressure condition.

## Branch

From the current default branch, create the deterministic branch
`claude/fq-<issue-number>`. Add an empty commit whose message includes the unique run ID,
then push it without force:

```bash
git switch -c claude/fq-<issue-number>
git commit --allow-empty -m "factory: claim FQ-<issue-number> (<run-id>)"
git push origin HEAD:refs/heads/claude/fq-<issue-number>
```

Two sessions may read the ready label at the same time. Their claim commits differ, so only
the first push can create the remote ref; a later push is rejected as non-fast-forward.
Treat that rejection as "already claimed" and stop. Never force the branch.

In a cloud session the `claude/` prefix is accepted for pushes. Do not add a slug or use a
different branch: the deterministic name is the lock.

## Implementing

Work in the smallest diff that satisfies `done_when`.

**Write the failing test first.** Not as ceremony: the test is what converts "I believe
this works" into a machine-checkable fact, and it is the artifact the verifier uses to
decide whether you actually fixed anything. If you cannot write a test that fails before
your change and passes after, say so explicitly in the PR body and flag the item for a
human read.

Rules while implementing:

- **Do not modify existing test files in an unattended run.** In an interactive session,
  stop and obtain explicit human approval before doing so. The PR stays draft and requires
  a human read.
- Do not add abstractions the item does not need. One caller means no interface.
- Do not clean up unrelated code. Note it for the queue instead.
- Do not add dependencies. If one is genuinely required, stop; that is a `ready-to-spec`
  decision.
- Stay inside `files_expected` where possible. Every file beyond it is a signal that the
  triage estimate was wrong, and if the count exceeds the charter's limit, stop.

## Gates

Run the gate level the queue item specifies:

```bash
./.claude/scripts/gates.sh full
```

Iterate until the final line reads `status=GREEN`. `status=MISCONFIGURED` blocks the run;
do not edit the gate configuration yourself to make it pass.

**You must quote the `FACTORY_GATES:` line verbatim in your PR body.** You may not
describe the result in your own words instead, and you may not report success if that line
says `status=RED`. If gates go red twice in a row on the same item, stop and hand it back
per the charter's `STOP_IF`.

Report optional skipped gates in the PR body. A required skip produces
`MISCONFIGURED`, so it cannot be mistaken for green.

Commit the scoped implementation and test after gates are green, then confirm both the
index and working tree are clean. The verifier's reversible negative-test proof refuses a
dirty checkout so it cannot hide or overwrite unrelated work.

## Independent verification

When gates are green, delegate verification to the `factory-verifier` subagent using the
Agent tool. Give it the queue item, branch name, and verified base SHA, **not your account
of what you did.** The verifier reads the diff cold and reaches its own verdict.

You may not skip this step because you are confident. Confidence is what it is checking.

If the verifier returns `verdict: rejected`, fix what it names and re-run gates and
commit the corrected diff before verification. After two rejections on the same item, stop and hand it to a human. Do not
argue with the verifier in a third pass; two failed attempts means the item was misclassified.

The verifier uses `./.factory/scripts/prove-test.sh` from a clean committed branch for the
negative test. Do not substitute `git stash`.

## Pull request

Open a PR only after gates are green and the verifier returns `verdict: accepted`.

PR body template. Fill every field. Empty fields are how unreviewed work gets merged.

```markdown
## What
<one sentence>

## Queue item
FQ-<n> - <link to issue>
done_when: <copied verbatim from the queue>

## Why this is safe
<the thing a reviewer would otherwise have to work out for themselves>

## Gates
<paste the FACTORY_GATES line verbatim>
Skipped gates: <list, or "none">

## Verification
Verifier verdict: accepted
<the verifier's one-line reasoning>

## Human read required
<yes + reason, or no>

## Not done
<anything in scope you deliberately left out, or "nothing">
```

Mark the PR as **draft** if any of these hold:

- the change touches a load-bearing path beyond a new test file allowed by the charter's
  test-file rule
- an existing test file was modified
- a gate was skipped
- the verifier accepted with reservations

Then replace the source issue's `factory:in-progress` label with
`factory:awaiting-review`, link the PR on the issue, and write one unique `implement` run
record under `docs/factory/runs/`.

If the run stops after claiming the issue, move it to the correct live state before ending:

- ambiguity or missing human decision -> `factory:needs-info`
- load-bearing or scope decision (other than the charter's new-test-file exception) ->
  `factory:ready-to-spec`
- transient infrastructure failure with no code PR -> `factory:ready-to-implement`

Never leave an issue `factory:in-progress` without a run record explaining who owns it.

## What you never do

- Merge. Ever. On any tier. The merge decision is the human's, and it is the one place
  accountability actually lives.
- Modify `docs/factory/CHARTER.md`.
- Modify anything under `.claude/`.
- Modify `.factory/gates.conf`, `AGENTS.md`, `.agents/`, or `.codex/`.
- Pick up a second item.
