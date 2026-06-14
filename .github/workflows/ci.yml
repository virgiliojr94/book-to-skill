name: CI

on:
  push:
    branches: [master]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    name: test (py${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install pytest
        run: pip install pytest
      - name: Run test suite
        run: pytest tests/ -q

  lint:
    name: lint (ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Install ruff
        run: pip install ruff
      - name: Ruff check
        # High-value gate: syntax errors (E9, e.g. IndentationError) + pyflakes
        # (F: undefined names, unused imports). Style rules are intentionally
        # not gated yet to avoid blocking on cosmetic churn.
        run: ruff check --select E9,F --target-version py310 scripts/ tests/

  smoke:
    name: smoke (dependency-free extraction)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Extract a sample with no optional deps installed
        run: |
          set -euo pipefail
          mkdir -p sample
          printf '# Backpressure\n\nChapter 1\nBounded queues prevent overload.\n' > sample/note.md
          export BOOK_SKILL_WORKDIR="$RUNNER_TEMP/work"
          python3 scripts/extract.py sample/note.md --mode text --install-missing no
          test -f "$BOOK_SKILL_WORKDIR/full_text.txt"
          test -f "$BOOK_SKILL_WORKDIR/metadata.json"
          grep -q "Backpressure" "$BOOK_SKILL_WORKDIR/full_text.txt"

  security:
    name: security (bandit + zizmor)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Install scanners
        run: pip install bandit zizmor
      - name: Bandit — gate on HIGH severity
        # Hard gate: only HIGH-severity / MEDIUM-confidence findings fail CI, to
        # avoid blocking on the known-acceptable subprocess (pip install) calls.
        # Ratchet down to medium once the open B314 docx-XML finding is hardened.
        run: bandit -q -r scripts tools --severity-level high --confidence-level medium
      - name: Bandit — report MEDIUM+ (informational)
        run: bandit -q -r scripts tools -ll || true
      - name: Zizmor — workflow audit (informational)
        # Surfaces GitHub Actions risks (injection, pull_request_target misuse).
        # Currently only flags unpinned-uses (tags vs SHA) — non-blocking until
        # the actions are pinned to SHAs (Dependabot follow-up).
        run: zizmor .github/workflows/ || true

  validate-skill:
    name: validate SKILL.md (Claude Code rules)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Audit SKILL.md against Claude Code skill rules
        # Fails on Claude-breaking issues (missing name/description, oversized
        # description, a tool restriction that omits Bash while the skill shells
        # out). Cross-agent metadata Claude ignores is reported as WARN only.
        run: python3 tools/validate_skill.py SKILL.md
