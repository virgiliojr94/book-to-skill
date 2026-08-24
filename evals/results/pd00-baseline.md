# PD-00 Discovery-Tax Baseline

## Fixture and source safety

Fixture: [`../fixtures/pd00-synthetic-book.txt`](../fixtures/pd00-synthetic-book.txt).
It is a deterministic, synthetic three-chapter text written for this evaluation.
No copyrighted book text is included or used.

## Reproduction

Exact command:

```sh
python3 tools/discovery_tax.py --full-text evals/fixtures/pd00-synthetic-book.txt --target-chapter 3 --core-tokens 4000
```

Environment: Python 3.12.3; `tiktoken` was not installed. Token method:
`words/0.75 heuristic (tiktoken not installed)`, selected by the current
`tools/discovery_tax.py` fallback.

Current output:

```text
Discovery Loop Tax — measured on a real book
  token method : words/0.75 heuristic (tiktoken not installed)
  source       : pd00-synthetic-book.txt
  chapters      : 3 detected
  target        : chapter 3  (Capítulo 3 — Verificação)
  book total    : 180 tokens
  Cost to answer ONE targeted question (tokens entering context):
    context-dump      :       180   (resident, re-billed EVERY turn)
    discovery (best)  :        53   ToC (1) + raw target chapter (52)
    discovery (loop)  :       106   + 1 prior chapter for a missing definition (53)
    book-to-skill     :     5,000   core [design cap (no --skill-dir)] (4,000) + compiled chapter (1,000)
  book-to-skill advantage:
    vs context-dump   : 0.0x fewer tokens
    vs discovery best : 0.0x fewer tokens
    vs discovery loop : 0.0x fewer tokens
  Note: the discovery figures are a model using the book's real ToC/chapter
  sizes; a single read, not a recurring cost. context-dump recurs every turn.
```

## Classification

**Measured:** fixture identity; three chapters detected; text sizes counted by
the tool's stated fallback tokenization method; and this command's deterministic
stdout for this environment.

**Modeled:** `discovery (best)` and `discovery (loop)` are discovery-path cost
models, not observations of an agent trajectory. `book-to-skill` uses the
configured 4,000-token core design cap plus a 1,000-token compiled-chapter
allowance because no `--skill-dir` was supplied. The reported advantages are
therefore modeled comparisons, not performance measurements.

This baseline does not authorize any paper-derived production change.
