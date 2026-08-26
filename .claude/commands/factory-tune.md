---
name: factory-tune
description: Review factory performance and propose deliberate constraint changes - tighten where a gate let something through, loosen where a class of change has been green long enough.
---

Constraints set once become either a permanent tax or a permanent hole. This command is the
scheduled review that keeps them honest. Run it monthly, or after any escaped defect.

It **proposes**. It never edits `CHARTER.md` itself. A factory that can rewrite its own
constraints has none.

## Gather evidence

Look at the last 30 days (or since `LAST_REVIEWED` in the charter). Use immutable records
under `docs/factory/runs/` plus GitHub issue and PR timestamps:

1. **Merged factory PRs.** How many, and how many needed human fixes after merge?
2. **Escaped defects.** Anything that reached the default branch and later needed a fix.
   For each, trace which gate should have caught it. This is the single most valuable
   input here.
3. **Rejected verifications.** What did the verifier catch, and is there a pattern? A
   repeated catch is a candidate for a new deterministic gate, which is strictly better
   than catching it with a model every time.
4. **Triage accuracy.** Items marked `ready-to-implement` that turned out to need a spec.
   A high rate means the charter's `AUTOMATABLE` list is too generous.
5. **Review queue depth over time.** Was the human review queue the bottleneck?
6. **Gate configuration.** Which runs were `MISCONFIGURED`? Which optional gates reported
   `SKIP`, and should any become required?
7. **Flow.** Median queue age, implementation duration where records are complete, and
   time from `awaiting-review` to the human decision. State when records are incomplete;
   do not manufacture precision.

## Propose

### Tighten when

- An escaped defect traces to an automated gate you trusted. **Say exactly which gate and
  what it missed.** Tighten immediately; this is not a judgment call.
- A category keeps arriving in review needing real fixes.
- The verifier catches the same class of problem repeatedly. Propose the deterministic
  check that would catch it instead, because a gate cannot be talked out of its verdict and
  a reviewer can.

### Loosen when

- A class of change has been green across a long enough run with no escapes. Name the run:
  "23 dependency bumps over 6 weeks, zero escapes, zero human fixes." Anecdote is not
  evidence.
- A rule is producing false stops without ever having prevented a real defect.

### Never loosen

- The merge gate
- Load-bearing path protection
- The test-modification rule
- The requirement that verification be a separate agent from implementation

These are structural. They are not tuned by throughput data because the thing they protect
against does not show up in throughput data until it is expensive.

## Output

```markdown
## Factory tuning - <date>

### Evidence
- Factory PRs merged: <n> (human fixes after merge: <n>)
- Escaped defects: <n>
- Verifier rejections: <n>  most common cause: <x>
- Triage accuracy: <n>% correctly routed
- Review queue: <avg> / <max> against a charter limit of <n>
- Gate misconfigurations: <n>  optional skips: <list>
- Median queue age: <duration>  median review wait: <duration>

### Proposed: tighten
1. <change> - because <the specific escape or pattern>

### Proposed: loosen
1. <change> - because <the run of evidence, with numbers>

### Proposed: new deterministic gate
1. <check> - replaces a judgment the verifier has made <n> times

### Not proposed but worth saying
<anything the data shows that no rule change fixes>
```

Write the accepted result to `docs/factory/DECISIONS.md` with the date and the evidence, so
the next review can tell whether a past loosening was a mistake. Then ask the human to
update `CHARTER.md` and its `LAST_REVIEWED` date.

## The honest question

End every run by asking it explicitly: **is the factory producing work worth the review
attention it consumes?** Volume is not the metric. If the queue is full of green PRs nobody
has time to read, the correct tuning is to produce less, not to review faster.
