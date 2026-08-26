---
name: factory-spec
description: Turn a ready-to-spec queue item into an approved plan through explicit human gates. Use when an item needs scope decided before code exists, when planning a feature, or before starting a migration. Runs interactively - not for unattended routines.
---

# Factory spec

This skill exists because the cheapest place to fix a decision is before any code encodes
it. Once a model has written a thousand lines, changing direction is expensive and every
instinct is to patch instead.

**This skill is interactive.** It stops and waits for a human. Do not run it inside an
unattended routine; a routine that approves its own spec has no gates at all.

Read `docs/factory/CONTRACT.md` and `docs/factory/CHARTER.md` before gate 1.

## Gates

Four, in order. Stop at each one. Never merge two gates into a single pass. Never proceed
on an inferred approval: "looks good" on gate 1 is not approval of gate 2.

Write each gate's output into `docs/factory/specs/FQ-<n>/` as its own file, and track
approvals in `docs/factory/specs/FQ-<n>/00-status.md`.

### Gate 1 - Product (`01-product.md`)

No technical content whatsoever. If you find yourself naming a file or a function, you are
in the wrong gate.

- The user problem, stated as a person's problem
- What success looks like, measurably
- A short announcement written as if the change already shipped
- Plain HTML mockups for any screen involved, in `mockups/`
- **What we are deliberately not doing**

That last item is the one people skip and the one that saves the most time. It is also
where the kill decision lives: if the honest answer to "should this exist" is no, this gate
is where that is cheap to say.

**STOP. Ask for approval.**

### Gate 2 - Architecture (`02-architecture.md`)

- Which existing systems and modules this touches
- New endpoints, data structures, and their shapes
- The end-to-end call flow, in order
- External dependencies, and whether each is genuinely required
- Which `LOAD_BEARING` paths are involved
- What could break elsewhere

**STOP. Ask for approval.** For anything touching a load-bearing path, also run the
`factory-critic` subagent against this document before asking, and include its output.

### Gate 3 - Program design (`03-design.md`)

- Exact file paths, new and modified
- Type signatures and function contracts, **no implementations**
- The call stack for the main flow
- The test list: what will be tested and what each test proves
- **The three decisions you are least confident about**

That last section is the highest-value part of this gate. It is where a reviewer can
intervene before the uncertainty is buried under working code.

**STOP. Ask for approval.**

### Gate 4 - Slices (`04-slices.md`)

Decompose into vertical slices. Each slice must be independently shippable, independently
testable, and small enough to review in one sitting.

- **Slice 0 is a tracer bullet**: end to end, mostly mocked, proving the shape works.
- Each later slice replaces one mock with real behavior.
- Each slice gets its own queue entry with its own `done_when`.

Once approved, create or update one GitHub issue per slice and apply
`factory:ready-to-implement`. Create or update its `factory-handoff:v1` comment with the
approved `done_when`, expected files, gate level, and confidence. Also write each slice into
the `QUEUE.md` snapshot. The issue label and comment are the handoff back to the unattended
part of the factory.

**STOP. Ask for approval before writing the queue entries.**

After the approved handoff, write a unique `spec` run record under `docs/factory/runs/`.

## Status file

`00-status.md` tracks state so the spec survives a context reset or a week away:

```
item: FQ-<n>
gate_1_product: approved 2026-08-16 | pending | rejected
gate_2_architecture: pending
gate_3_design: not-started
gate_4_slices: not-started
slices_completed: 0 / ?
open_questions:
  - <anything blocking, with who owns the answer>
```

## For migrations specifically

If this spec covers a migration, gate 2 must answer one question before anything else:

**What is the oracle?**

An old or unlaunched project usually has the thinnest test coverage in the portfolio, which
means a migration can compile, typecheck, pass every existing test, and still behave
differently. Green does not mean equivalent.

So the first slices are not migration slices:

1. Make it build on the current stack
2. Make it typecheck
3. Pin current behavior with characterization tests and golden-master snapshots
4. **Only then** migrate, wide and fast, against the oracle you just built

This inverts the usual reading of back-pressure. Instead of accepting the verification
budget you have and limiting autonomy to match, you go build a bigger budget first and
claim the autonomy it buys. Each of those four steps is itself a clean factory job.

If gate 2 cannot name the oracle, the migration is not ready and no amount of agent
throughput fixes that.
