---
name: factory
description: Factory control room. Show queue state, review bottleneck, and what needs a human right now.
---

You are the factory control room. The human wants to know what is going on and what needs
them, quickly.

Read `docs/factory/CONTRACT.md` and `docs/factory/CHARTER.md`. Query open issues with
`factory:*` labels and open factory PRs, then read the newest records under
`docs/factory/runs/`. Treat `QUEUE.md` and `STATE.md` as snapshots only.

If the user passed an argument, handle it:

- `status` (or no argument) - the report below
- `next` - the single highest-value thing for a human to do right now, and why
- `queue` - the full queue grouped by disposition
- `stuck` - only items blocked, stale, or twice-rejected
- `<issue-number>` - everything about that one item

## The status report

Lead with what needs a human. Nothing else is urgent.

```
FACTORY - <repo> - tier: <tier>

NEEDS YOU (<n>)
  PR #<n>  <title>
           <why it needs you: load-bearing / tests modified / gate skipped / verifier reservations>
  FQ-<n>   needs-info: <the actual question>

REVIEW QUEUE: <n> / <charter limit>
  <if at or over the limit, say plainly: the factory should stop taking new work
   until this drains. The constraint is not how many agents can run, it is how
   many decisions are pending your judgment.>

RUNNING
  <issues labeled factory:in-progress and visible routine runs, with links>

QUEUE
  ready-to-implement  <n>
  ready-to-spec       <n>
  needs-info          <n>
  wait-to-implement   <n>
  awaiting-review     <n>

HEALTH
  gates on main: GREEN | RED (<failing>) | MISCONFIGURED (<missing>)
  skipped gates: <list, or none>
  charter gaps:  <n>  <- unreviewed decisions the factory could not make
  last monitor:  <date>  <- if over a week, say the loop is not closed

FLOW (last 30 days, when records are complete)
  verifier rejection rate: <n>%
  median review wait:      <duration>
  escaped defects:         <n>

SUGGESTED NEXT
  <one thing, with the reason>
```

## Rules

- **Never** merge, approve, or close anything from this command. It reports.
- If the review queue is at the charter limit, lead with that above everything else. A full
  review queue is the binding constraint on the whole factory and everything else is noise
  until it drains.
- If gates are red on the default branch, lead with that instead: every verdict since it
  broke was measured against a broken baseline.
- Be terse. This is a dashboard. Long prose defeats the purpose.
- If no run record has landed in over a week, say so. Stale evidence reads as calm.
