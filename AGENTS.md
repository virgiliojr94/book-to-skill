# AGENTS.md

This file is the repository-wide execution contract for coding agents.

## Project intent

`book-to-skill` converts books and documents into structured, on-demand Agent Skills. The repository has two distinct halves:

1. a deterministic Python extractor (`scripts/extract.py` -> `book_to_skill/`), and
2. a spec-driven generator (`SKILL.md`) executed by an agent.

Do not blur those responsibilities without a measured reason.

## Sources of truth

Before changing code, read the smallest relevant set of files:

1. `CONTRIBUTING.md` — contribution rules and required checks.
2. `docs/architecture.md` — current architecture and component ownership.
3. `SKILL.md` — only when generation behavior or generated-skill structure is in scope.
4. `SECURITY.md` and `SECURITY-NOTICE.md` — when touching parsing, files, subprocesses, generated content, or dependencies.
5. Existing tests closest to the code being changed.

For the progressive-disclosure research/evaluation initiative, also read:

- `docs/research/progressive-disclosure-evals.md`

That document is the execution ledger and defines task order, evidence gates, and which paper-derived ideas are hypotheses rather than product requirements.

## Non-negotiable rules

- **Measure, do not assert.** No claimed quality, token, routing, accuracy, or cost improvement without reproducible evidence.
- **Do not turn a paper hypothesis into production behavior before its gate passes.** In particular, do not add KEY_ELEMENTS-style metadata, library mode, deeper routing, or new `SKILL.md` content merely because it sounds plausible.
- **Keep `SKILL.md` lean.** It is always-loaded converter context. Any net growth needs evidence that the added context earns its cost.
- **Never commit raw copyrighted book text.** Use synthetic, public-domain, or explicitly licensed fixtures. Keep private evaluation corpora and raw live trajectories out of git.
- **Avoid new runtime dependencies for evaluation work.** Evaluation-only dependencies belong outside the core runtime and must be justified.
- **Do not edit `CHANGELOG.md` by hand.**
- Preserve backwards compatibility unless the task explicitly authorizes a breaking change.
- Do not weaken security checks, path hardening, sanitization, or generated-skill scanning to make an experiment pass.

## Execution loop

For any non-trivial task, use this loop. Do not skip directly from idea to implementation.

1. **Orient**
   - Read this file and the relevant source-of-truth files.
   - Inspect current code/tests before proposing new modules or abstractions.
   - For research-plan work, locate the first task whose status is `READY` and whose dependencies are complete.

2. **Plan the smallest coherent change**
   - State the hypothesis or bug being addressed.
   - State what will *not* change.
   - Prefer reuse of existing utilities over parallel implementations.
   - Define the acceptance command(s) before editing code.

3. **Implement one task**
   - Keep the diff focused.
   - Add deterministic tests with the implementation.
   - Do not opportunistically refactor unrelated code.

4. **Prove it**
   - Run the task-specific checks.
   - Run the repository gates below.
   - Capture actual command output or machine-readable result artifacts; prose such as "looks good" is not evidence.

5. **Record state**
   - Update the task status/evidence section in the research plan when that plan is in scope.
   - Record blockers as blockers; never mark a task complete because the intended code was written.

6. **Continue only after the gate is green**
   - Move to the next dependency-ready task only after the current task is proven.
   - Respect PR boundaries defined in the plan. A task that changes production behavior must not be silently bundled with unrelated research infrastructure.

## Validation gates

Minimum local checks for code changes:

```bash
pytest -q
ruff check .
```

If `SKILL.md` changes:

```bash
python3 tools/validate_skill.py SKILL.md
```

If extraction behavior changes, also run the relevant extractor smoke/reproduction command and its targeted tests.

If generated-skill behavior changes, provide a before/after generated artifact or benchmark result that demonstrates the intended difference without committing copyrighted source text.

A task is not `DONE` if a required check is skipped, failing, or replaced by an unverified claim.

## Evaluation-work cost discipline

Live model experiments are expensive and are never the first validation step.

- Unit/fixture tests first.
- Small discriminating sample before a large sweep.
- Cache/reuse generated packs keyed by source/config/model/prompt identity.
- Pre-register the condition, corpus, questions, model/harness, repetitions, and token/cost ceiling before a live run.
- Do not jump to 10/20-book sweeps before smaller-scale gates justify them.
- If a cheaper test can falsify the hypothesis, run it first.

## Instruction scope

This root file applies repository-wide. A more deeply nested `AGENTS.md` may add narrower instructions for its subtree; the more specific file wins when instructions conflict. Direct user/system instructions take precedence over repository guidance.
