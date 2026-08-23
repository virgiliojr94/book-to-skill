# Progressive Disclosure Evaluation Plan

Status: **ACTIVE PLAN — planning only; no paper-derived production change is authorized by this document**

Primary source: [He et al., *Is Progressive Disclosure All You Need for Long-Context Agents?*](https://arxiv.org/abs/2607.17598)

This plan converts the paper's useful findings into a sequence of falsifiable, low-waste experiments for `book-to-skill`. It is intentionally written so another coding agent can resume from the repository, locate the next task, implement it, prove it, record evidence, and continue without reconstructing the entire discussion.

The goal is not to copy the paper's implementation. The goal is to answer the questions the paper leaves open for the **current** `book-to-skill` architecture.

---

## 1. Why this work exists

The repository already has `tools/discovery_tax.py`, which models context cost using real extracted chapter sizes. That tool is useful, but its own documentation correctly says the discovery-loop numbers are a **model**, not a measurement of a real agent trajectory.

The next useful step is therefore not another token-saving claim or another generation feature. It is a small evaluation system that can tell us, with evidence:

1. whether the agent finds the right source/book/chapter;
2. whether the representation helps after the correct material is reached;
3. what files/tools the agent used;
4. what the run cost in tokens/calls;
5. whether a proposed change beats the existing behavior under the same conditions.

Only after those measurements should a paper-inspired idea change production `SKILL.md` behavior.

---

## 2. What the paper supports vs. what remains open

### Supported by this paper

The plan may treat these as findings of the cited experiment, with the paper's scope limitations intact:

- The authors evaluate a **controlled recipe based on book-to-skill**, not this repository's full current generator. Their recipe chunks by document structure (fallback ~4,000 words), generates a short summary plus `KEY_ELEMENTS`, and routes to raw chunk text.
- A single-level/flat skill pack is the best default in the study overall; pushing chunk descriptions into always-loaded child skills can create context pressure and can hurt.
- The value of progressive disclosure depends on the harness. On a single book, a strong navigator such as the tested Codex setup can reconstruct `grep -> locate -> read` itself, reducing the accuracy benefit of the pre-built pack.
- At multi-book scale, especially English open QA in the tested setup, flat disclosure degrades more slowly than raw navigation.
- The paper's `KEY_ELEMENTS` field was **used**, but its independent contribution was **not ablated**.
- The paper does **not** validate the current `book-to-skill` semantic representation: frameworks, mental models, anti-patterns, decision rules, glossary/patterns/cheatsheet, and the current chapter template were not the independent variable.
- The paper explicitly does not establish transfer to code, technical manuals, or other non-narrative corpora.
- Cost results such as the K=20 En.QA `68.3M` vs `32.5M` token comparison are condition-specific uncached measurements, not a universal 2x claim.

### Important nuance from the appendix

Do not encode the slogan "hierarchy never helps" as a product invariant. The paper's appendix contains task/scale-specific cells where deeper routing recovers or leads (for example some Pi open-QA conditions). The safe design conclusion is:

> **Flat is the default to beat. Deeper routing is an experiment, not a forbidden architecture and not a production requirement.**

### Open questions for this repository

These are hypotheses until this plan produces evidence:

- Does the current structured representation improve **application/decision** tasks compared with the paper-style `summary + key elements + raw chunk` representation?
- Does adding exact routing terms/entities improve routing enough to justify extra always/activation-loaded context?
- Can explicit/forced activation separate routing failure from representation/reasoning failure?
- Do the paper's scaling patterns reproduce on technical books, documentation, or SOP-like material?
- Is a library-level index useful for actual `book-to-skill` collections?
- Does a structured chapter plus access to source evidence outperform either structure-only or raw-only?
- Does different chunk granularity matter after routing and representation are controlled?

---

## 3. Research rules: keep causal questions separable

Do not change multiple design axes in the same comparison.

Use this decomposition:

```text
SOURCE
  -> CHUNKING
  -> ROUTING METADATA
  -> DISCLOSURE DEPTH
  -> ON-DEMAND REPRESENTATION
  -> HARNESS ACTIVATION/NAVIGATION
  -> ANSWER/DECISION
```

A valid experiment changes one highlighted axis while holding the others fixed as far as the harness allows.

Examples:

- To test **representation**, keep chunk boundaries and routing index identical; change only the payload opened after routing.
- To test **routing metadata**, keep chunk payloads identical; change only index metadata.
- To test **activation**, keep the pack identical; compare automatic discovery with explicit activation where the harness supports it.
- To test **chunking**, keep the routing/representation recipe fixed while changing boundaries.

If a harness cannot hold a variable constant, record the confound rather than claiming causal isolation.

---

## 4. Cost discipline: no more expensive runs without a decision they can change

Every live-model run must have a pre-run config/manifest containing:

- source/corpus ID and hash;
- condition name;
- question set ID and hash;
- model and harness;
- generation model if different from answer model;
- prompt/config hashes;
- repetition/seed information when supported;
- `max_calls`;
- `max_input_tokens`;
- `max_output_tokens`;
- optional `max_cost_usd` if current pricing is supplied by the operator;
- reason this run is necessary and what decision it can change.

The runner must stop rather than silently exceed a configured hard ceiling.

Run order for any new experiment:

1. unit tests / fixture replay;
2. one or a few smoke questions;
3. smallest discriminating corpus;
4. repeat only if variance/instability requires it;
5. larger K or broader sweep only after the smaller run produces a reason to continue.

Never start with a 20-book sweep.

Generated packs should be reused when source/config/model/prompt identity matches. Do not pay to regenerate identical inputs.

---

## 5. Planned repository shape

This is the intended shape, not existing code. A task may adjust paths if the repository changes, but the plan must be updated before diverging.

```text
tools/evals/
  manifest.py          # stable run manifest + hashes + budget fields
  score.py             # deterministic metrics where possible
  replay.py            # replay recorded/synthetic trajectories without APIs
  paper_flat.py        # paper-style baseline pack builder
  run.py               # experiment orchestration / dry-run / budget gate
  adapters/            # live harness adapters, added only when justified

tests/evals/
  ...                  # deterministic unit/integration tests

evals/
  fixtures/            # synthetic/public-domain/licensed tiny fixtures only
  configs/             # committed experiment configs, no secrets
  results/             # small aggregate summaries/manifests only

.eval-work/            # local raw trajectories, generated packs, private corpora; gitignored
```

Evaluation code must not become a runtime dependency of `book-to-skill` unless a later production decision explicitly promotes part of it.

---

## 6. Core metrics

Do not reduce an experiment to final answer accuracy.

Record what the harness exposes, including:

### Routing/navigation

- skill discovered/activated (when observable);
- target book selected;
- target chapter/chunk selected;
- files opened;
- irrelevant files opened before target;
- tool calls (`grep`, read/open, search, etc. when observable);
- time/calls until first relevant evidence.

### Outcome

- exact/deterministic answer score where a gold answer exists;
- task-specific rubric result for application/decision tasks;
- whether correct source evidence was reached before an incorrect answer.

### Efficiency

- input tokens;
- output tokens;
- total calls;
- elapsed time when comparable;
- current estimated monetary cost only when pricing is explicitly recorded with a date/source;
- cached vs uncached usage separately if the host exposes it.

### Representation diagnostics

When the correct chunk was opened but the answer is wrong, classify only when supported by observable evidence:

- evidence present but reasoning/answer failed;
- structured representation omitted required evidence;
- routing chose the wrong material;
- unknown/ambiguous.

Do not infer hidden reasoning from an answer string.

---

## 7. Task ledger

Status values:

- `READY` — dependencies complete; next agent may take it.
- `BLOCKED` — wait for listed dependencies.
- `IN_PROGRESS` — one agent owns it; include branch/PR in Evidence Ledger.
- `DONE` — all acceptance gates proven.
- `REJECTED` — hypothesis/approach failed; preserve evidence and reason.

| ID | Status | Task | Depends on | Production change? |
|---|---|---|---|---|
| PD-00 | READY | Freeze current baseline and evaluation contract | none | no |
| PD-01 | BLOCKED | Implement deterministic manifest + hashing + budget schema | PD-00 | no |
| PD-02 | BLOCKED | Implement fixture/replay scorer with trajectory metrics | PD-01 | no |
| PD-03 | BLOCKED | Implement paper-flat baseline pack builder | PD-01 | no |
| PD-04 | BLOCKED | Add dry-run/live runner contract and first harness adapter | PD-02, PD-03 | no |
| PD-05 | BLOCKED | Representation experiment: raw payload vs structured B2S payload | PD-04 | no |
| PD-06 | BLOCKED | Automatic vs explicit activation experiment | PD-04 | no |
| PD-07 | BLOCKED | Routing metadata ablation | PD-04 | no |
| PD-08 | BLOCKED | Technical/non-narrative corpus replication | PD-05, PD-07 | no |
| PD-09 | BLOCKED | Library scaling experiment | PD-04, PD-08 | no |
| PD-10 | BLOCKED | Optional Hybrid RAG reference baseline | PD-04 | no |
| PD-11 | BLOCKED | Chunking ablation | PD-08 | no |
| PD-12 | BLOCKED | Evidence review and production decision(s) | relevant experiments | **decision only** |

---

## 8. Task specifications

### PD-00 — Freeze current baseline and evaluation contract

**Goal**

Create a zero-API baseline snapshot before writing new eval infrastructure.

**Required actions**

1. Run current repository checks.
2. Run/inspect `tools/discovery_tax.py` on a license-safe fixture or existing allowed local source if available; do not commit copyrighted source text.
3. Record what the current tool measures vs models.
4. Record current generator architecture from `docs/architecture.md` and `SKILL.md` without changing them.
5. Choose a tiny synthetic/public-domain fixture set for deterministic eval development.

**Acceptance**

```bash
pytest -q
ruff check .
python3 tools/validate_skill.py SKILL.md
```

Plus a committed small baseline note/manifest that contains no raw copyrighted material and clearly labels modeled vs measured numbers.

**Do not** modify production generation behavior in this task.

---

### PD-01 — Deterministic run manifest, hashing, and budgets

**Goal**

Make every later result attributable and reusable.

**Minimum fields**

- schema version / run ID;
- source IDs + content hashes;
- condition;
- question-set hash;
- model/harness identifiers;
- prompt/config hashes;
- seed/repetition fields with explicit `unsupported` where applicable;
- token/call/cost ceilings;
- code version/commit SHA if available;
- artifact/result paths.

**Requirements**

- standard-library implementation unless a dependency is demonstrably needed;
- stable serialization;
- deterministic hash tests;
- no secrets in committed manifests;
- invalid/missing required fields fail clearly.

**Acceptance**

Targeted tests prove identical inputs generate identical identities and meaningful config changes alter the identity. Full `pytest -q` and `ruff check .` pass.

---

### PD-02 — Fixture/replay scorer

**Goal**

Prove scoring and trajectory accounting without spending model tokens.

Use tiny synthetic trajectories that represent:

- correct routing + correct answer;
- wrong book/chapter routing;
- correct evidence reached + wrong answer;
- multiple irrelevant opens before target;
- missing/unknown observability.

**Output**

Machine-readable aggregate and per-question results. The scorer must not guess unobserved states.

**Acceptance**

Tests cover every classification above and token/call aggregation. A replay command produces stable JSON on repeated runs.

---

### PD-03 — Paper-flat baseline builder

**Goal**

Create a reproducible baseline matching the paper's *experimental representation* closely enough for controlled comparisons, without pretending it is the repository's current generator.

**Baseline structure**

- one root `SKILL.md`;
- book-level description for discovery;
- activation-time table/index of chunk path + short description;
- per-chunk `SUMMARY` and optional `KEY_ELEMENTS` metadata in the index;
- raw chunk payload files loaded on demand;
- source-structure chapter split with an explicit fallback policy.

Generation of summary/KEY_ELEMENTS may require a model in live mode; tests must use fixed fixture outputs so CI remains offline/deterministic.

**Critical rule**

Do not add this representation to production `SKILL.md`. It is an experiment baseline.

**Acceptance**

Given the same fixture and fixed metadata, builder output is stable and contains exactly one routing level. Tests verify no child-skill hierarchy is introduced.

---

### PD-04 — Runner contract + first live harness adapter

**Goal**

Run `raw`, `paper-flat`, and a provided/frozen current-B2S pack under the same question/config envelope and record observable trajectory/cost data.

**Before choosing an adapter**

Inspect available upstream tooling. Prefer compatibility with an existing agent protocol/environment (for example ACP/LOONGDOC if accessible and reusable) over inventing a bespoke harness.

**Runner must support**

- `--dry-run` with planned conditions/calls/budgets and no model calls;
- hard call/token budget gates where host usage data allows enforcement;
- local work directory outside git;
- one condition at a time;
- result/manifest emission even on controlled failure;
- adapter capability declaration (files opened observable? activation observable? tokens observable? forced activation supported?).

**Acceptance**

Fixture/replay adapter is green first. Then one intentionally tiny live smoke run may be performed within a declared budget. No large sweep.

---

### PD-05 — Representation experiment (highest-priority research question)

**Question**

Once routing is held constant, does the current structured `book-to-skill` payload help an agent *apply* knowledge better than raw chapter text or a simple representation?

**Conditions**

Keep the same source, chunk boundaries, root routing metadata, harness, model, questions, and activation condition. Change only on-demand payload:

1. `RAW_CHUNK` — raw chunk text;
2. `SIMPLE` — simple summary representation;
3. `B2S_STRUCTURED` — current structured chapter representation;
4. `B2S_STRUCTURED_WITH_SOURCE_FALLBACK` — structured representation plus access to source evidence, if the harness can make this comparison without changing routing.

If condition 4 cannot be isolated cleanly, defer it rather than contaminate the primary comparison.

**Task families**

Use questions that distinguish representation types:

- factual retrieval;
- explanation/understanding;
- application to a scenario;
- decision/trade-off using source criteria;
- anti-pattern/counter-example.

**Promotion rule**

No production claim from one dataset/cell. Record task-family-specific effects and variance. A null result is a valid outcome.

---

### PD-06 — Automatic vs explicit activation

**Question**

How much failure comes from discovering/routing to the Skill versus using the knowledge after the correct Skill is made available?

Run the same pack/questions under:

- `AUTO` — normal host discovery/activation;
- `FORCED` — correct Skill explicitly activated/provided, **only if the harness supports a clean forced condition**.

If forced activation is not supported, mark the adapter capability false and do not simulate a supposedly equivalent mechanism without documenting the difference.

**Output**

Separate routing/activation success from downstream answer performance as far as observability allows.

---

### PD-07 — Routing metadata ablation

**Question**

Which metadata earns its context cost?

Keep the same chunk payload and boundaries. Compare, in order:

1. `SUMMARY_ONLY`;
2. `SUMMARY_EXACT_TERMS`;
3. `SUMMARY_KEY_ELEMENTS` (paper-style);
4. `CURRENT_B2S_INDEX` or a precisely defined projection of it.

Record both routing success and metadata token overhead.

**Important**

`KEY_ELEMENTS` is not a validated production requirement. This experiment exists because the paper did not isolate its effect.

**Production gate candidate**

Only consider adding/changing routing metadata if improvement repeats on more than one appropriate corpus/task family and the added context cost is reported. Otherwise keep the current behavior.

---

### PD-08 — Technical/non-narrative replication

**Question**

Do the useful paper effects transfer to the material `book-to-skill` is commonly designed to structure: technical books, docs, standards, and SOP-like content?

**Corpus requirements**

- public-domain, permissively licensed, synthetic, or explicitly authorized;
- at least two different structural/content types before drawing a product conclusion;
- avoid famous material as the only benchmark because parametric memory can hide retrieval/navigation failures.

Prefer held-out/synthetic facts for routing tests where practical.

**Acceptance**

Run the already-defined conditions; do not add new features during the replication. Publish aggregate manifests/results that are legally safe to commit.

---

### PD-09 — Library scaling

**Question**

When does a collection-level index become useful for real non-narrative `book-to-skill` material?

Do not implement `library-to-skill` in production first.

Experimental conditions may include:

1. no library index;
2. one-line-per-source index similar to the paper's `corpus-index.md` setup;
3. richer semantic library index, only after condition 2 is measured.

**Scale discipline**

Start K=1 and K=5. Proceed to K=10 only if the smaller run leaves a scaling question unresolved or shows a meaningful divergence. Proceed to K=20 only with a written justification and budget.

**Production gate candidate**

A library feature is justified only if the index provides reproducible benefit on real target-domain corpora and does not merely move excessive context into an always-loaded layer.

---

### PD-10 — Optional Hybrid RAG reference baseline

**Goal**

Provide an external retrieval reference, not a runtime feature.

The paper's reference stack used BM25 + BGE-M3 dense retrieval + reciprocal-rank fusion + BGE cross-encoder reranking. Reproduce or reuse that stack only when the agentic conditions are already stable enough that the comparison will answer a decision.

**Rules**

- keep heavy ML dependencies evaluation-only;
- prefer a separate optional environment/requirements file;
- do not claim "Skills beat RAG" from this baseline;
- report the exact retriever/embedding/reranker versions and budgets.

If this task costs more maintenance than the decision is worth, it may be explicitly `REJECTED` with rationale.

---

### PD-11 — Chunking ablation

Run only after representation/routing tests stabilize.

Compare a small set such as:

- source chapter/section boundaries;
- fixed-size paragraph-preserving chunks;
- structure-aware technical sections if the extractor exposes them reliably.

Hold routing metadata recipe and payload representation constant. Do not change extraction, routing, and representation simultaneously.

---

### PD-12 — Evidence review and production decisions

This is not a coding task. It is the gate that decides whether any experimental idea enters the product.

For each candidate, write one of:

- `ADOPT` — evidence justifies a focused production PR;
- `KEEP EXPERIMENTAL` — useful in some regimes, not a safe default;
- `REJECT` — no demonstrated value or unacceptable cost/complexity;
- `INSUFFICIENT EVIDENCE` — more data required, with the exact missing comparison.

Candidate decisions:

| Candidate production idea | Minimum evidence before `ADOPT` |
|---|---|
| Add exact terms / KEY_ELEMENTS-style routing metadata | PD-07 repeated benefit + context overhead measured |
| Change chapter representation/template | PD-05 task-family benefit without unacceptable retrieval regression |
| Add explicit library mode/index | PD-09 target-domain scaling benefit |
| Add deeper/adaptive hierarchy | Specific repeated task/scale benefit that beats flat after context cost |
| Add generation/eval manifest to normal product output | Demonstrated user/reproducibility value beyond eval tooling |
| Make RAG superiority claims | **Never universal**; only condition-specific benchmark statements with exact setup |

Any adopted feature gets its own focused PR with new tests and before/after evidence. Do not mutate multiple production surfaces in PD-12 itself.

---

## 9. Evidence Ledger

Agents update this table when a task changes status. Keep entries short; link to PR/commit/result paths rather than pasting long logs.

| Task | Status | PR / commit | Evidence | Notes |
|---|---|---|---|---|
| PD-00 | READY | — | — | First implementation task |
| PD-01 | BLOCKED | — | — | waits for PD-00 |
| PD-02 | BLOCKED | — | — | waits for PD-01 |
| PD-03 | BLOCKED | — | — | waits for PD-01 |
| PD-04 | BLOCKED | — | — | waits for PD-02/03 |
| PD-05 | BLOCKED | — | — | primary representation experiment |
| PD-06 | BLOCKED | — | — | host capability dependent |
| PD-07 | BLOCKED | — | — | no production metadata change before this |
| PD-08 | BLOCKED | — | — | target-domain replication |
| PD-09 | BLOCKED | — | — | no library feature before this |
| PD-10 | BLOCKED | — | — | optional reference baseline |
| PD-11 | BLOCKED | — | — | late ablation |
| PD-12 | BLOCKED | — | — | production decision gate |

---

## 10. Claims guardrail

Until evidence changes, do **not** publish or encode these as established facts:

- "The paper validated the full current book-to-skill generator."
- "KEY_ELEMENTS improves routing." (It was used, not independently ablated.)
- "book-to-skill uses 2x fewer tokens." (The cited ~2x result is one specific K=20 En.QA condition.)
- "Skills beat RAG." (The paper compared a specific hybrid baseline under specific tasks.)
- "Flat always beats hierarchy." (Flat is the best default overall; appendix effects are task/scale-specific.)
- "The results apply to technical books/code." (The paper explicitly leaves non-narrative transfer open.)
- "Structured frameworks/mental models/anti-patterns are better than summaries." (That is PD-05's question.)

Safe language must name the condition or say the question remains open.

---

## 11. Agent instruction compatibility

This repository now uses root `AGENTS.md` as the canonical agent execution contract.

Rationale based on current tooling documentation:

- The open [AGENTS.md](https://agents.md/) format is intended for repository instructions consumed by coding agents.
- OpenAI Codex scopes root `AGENTS.md` to the repository tree and allows deeper files to override narrower subtrees.
- Claude Code currently reads `CLAUDE.md`, not `AGENTS.md` directly, so the repository contains a minimal `CLAUDE.md` importing `AGENTS.md` rather than duplicating rules. See Anthropic's project-memory documentation: <https://code.claude.com/docs/en/memory>.

Keep the root instruction file compact. Detailed initiative state belongs here, not duplicated into every agent's always-loaded context.

---

## 12. Definition of complete

This research initiative is complete only when:

1. deterministic evaluation infrastructure exists and is tested;
2. at least one real harness produces inspectable trajectory/cost results under controlled conditions;
3. paper-flat and current-B2S comparisons have been run on legal/appropriate corpora;
4. routing vs representation is separated as far as supported by the harness;
5. technical/non-narrative replication has been attempted;
6. library scaling is either measured or explicitly rejected as not worth the cost;
7. every production candidate receives an `ADOPT / KEEP EXPERIMENTAL / REJECT / INSUFFICIENT EVIDENCE` decision;
8. any adopted behavior is implemented in separate focused PRs with tests/evidence;
9. public claims are updated only to what the measurements actually support.

The success criterion is **not** "all proposed features shipped." The success criterion is that we can identify which ideas earn their complexity and which should not enter `book-to-skill`.
