#!/usr/bin/env bash
# gates.sh - the factory's deterministic verdict.
#
# This is the one part of the pipeline that cannot be talked out of its verdict
# by a confident paragraph. Every factory skill calls it. Nothing merges without it.
#
# Usage:
#   ./.claude/scripts/gates.sh fast    # types + lint            (~seconds, run constantly)
#   ./.claude/scripts/gates.sh full    # + tests + build         (default, run before any PR)
#   ./.claude/scripts/gates.sh deep    # + audit + complexity    (run on load-bearing changes)
#
# Exit codes:  0 = all required gates green   1 = at least one gate red
#              2 = invalid level or a required gate could not run
#
# Output ends with a machine-readable line so an agent cannot paraphrase the result:
#   FACTORY_GATES: level=full status=RED passed=3 failed=1 failing=test skipped=build misconfigured=none
#
# Customise .factory/gates.conf and the DETECT block for your project.

set -uo pipefail

LEVEL="${1:-full}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 2

# The project documents a local virtualenv for its CI tools. Use it when present,
# but never install dependencies from the gate runner.
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

case "$LEVEL" in
  fast|full|deep) ;;
  *)
    echo "error: gate level must be fast, full, or deep (got: $LEVEL)" >&2
    printf 'FACTORY_GATES: level=%s status=MISCONFIGURED passed=0 failed=0 failing=none skipped=none misconfigured=invalid-level\n' "$LEVEL"
    exit 2
    ;;
esac

REQUIRED_FAST="types lint"
REQUIRED_FULL="types lint test"
REQUIRED_DEEP="types lint test audit architecture"
if [ -f .factory/gates.conf ]; then
  # This file is protected by the factory contract and contains assignments only.
  # shellcheck disable=SC1091
  source .factory/gates.conf
fi

case "$LEVEL" in
  fast) REQUIRED="$REQUIRED_FAST" ;;
  full) REQUIRED="$REQUIRED_FULL" ;;
  deep) REQUIRED="$REQUIRED_DEEP" ;;
esac

for gate in $REQUIRED; do
  case "$gate" in
    types|lint|test|build|audit|mutation|architecture) ;;
    *)
      echo "error: unknown required gate in .factory/gates.conf: $gate" >&2
      printf 'FACTORY_GATES: level=%s status=MISCONFIGURED passed=0 failed=0 failing=none skipped=none misconfigured=unknown-required-gate:%s\n' "$LEVEL" "$gate"
      exit 2
      ;;
  esac
done

PASSED=0
FAILED=0
FAILING=""
SKIPPED=""
MISCONFIGURED=""

c_red()   { printf '\033[31m%s\033[0m\n' "$1"; }
c_green() { printf '\033[32m%s\033[0m\n' "$1"; }
c_dim()   { printf '\033[2m%s\033[0m\n' "$1"; }

# run <name> <command...>  - runs a gate, records the verdict, never exits early.
run() {
  local name="$1"; shift
  printf '\n=== gate: %s ===\n' "$name"
  if "$@"; then
    c_green "PASS  $name"
    PASSED=$((PASSED + 1))
  else
    c_red   "FAIL  $name"
    FAILED=$((FAILED + 1))
    FAILING="${FAILING}${FAILING:+,}${name}"
  fi
}

skip() {
  c_dim "SKIP  $1 ($2)"
  SKIPPED="${SKIPPED}${SKIPPED:+,}$1"
  case " $REQUIRED " in
    *" $1 "*) MISCONFIGURED="${MISCONFIGURED}${MISCONFIGURED:+,}$1" ;;
  esac
}

has()      { command -v "$1" >/dev/null 2>&1; }
pkg_has()  { [ -f package.json ] && node -e "process.exit(require('./package.json').scripts?.['$1']?0:1)" 2>/dev/null; }

# ---------------------------------------------------------------------------
# DETECT - identify the project type. Edit this block for your repo.
# ---------------------------------------------------------------------------
STACK="unknown"
if   [ -f package.json ];      then STACK="node"
elif [ -f pyproject.toml ] || [ -f setup.py ]; then STACK="python"
elif [ -f Cargo.toml ];        then STACK="rust"
elif [ -f go.mod ];            then STACK="go"
fi

# book-to-skill has no project-wide type checker, and its CI defines a more
# specific lint/test/security contract than the generic Python defaults.
if [ "$STACK" = "python" ] && [ -d book_to_skill ] && [ -f tools/validate_skill.py ] && [ -f pyproject.toml ]; then
  STACK="book-to-skill"
fi

# Pick the package manager rather than assuming npm.
PM="npm"
if   [ -f pnpm-lock.yaml ];   then PM="pnpm"
elif [ -f yarn.lock ];        then PM="yarn"
elif [ -f bun.lockb ];        then PM="bun"
fi
[ "$STACK" = "book-to-skill" ] && PM="python"
PMRUN="$PM run"
[ "$PM" = "npm" ] && PMRUN="npm run --silent"

printf 'factory gates | level=%s stack=%s pm=%s\n' "$LEVEL" "$STACK" "$PM"

# ---------------------------------------------------------------------------
# TIER 1 - fast. Types and lint. Cheap enough to run on every edit.
# ---------------------------------------------------------------------------
case "$STACK" in
  node)
    if pkg_has typecheck;    then run types $PMRUN typecheck
    elif [ -f tsconfig.json ] && has npx; then run types npx --no-install tsc --noEmit
    else skip types "no typecheck script or tsconfig.json"; fi

    if pkg_has lint;         then run lint $PMRUN lint
    elif has npx && [ -f eslint.config.js -o -f eslint.config.mjs -o -f .eslintrc.json -o -f .eslintrc.cjs ]; then
                                  run lint npx --no-install eslint .
    else skip lint "no lint script or eslint config"; fi
    ;;
  book-to-skill)
    if has ruff; then
      run lint ruff check --select E9,F --target-version py310 book_to_skill/ scripts/ tests/ tools/
    else
      skip lint "ruff not installed"
    fi
    ;;
  python)
    if has ruff;  then run lint  ruff check .;  else skip lint  "ruff not installed"; fi
    if has mypy;  then run types mypy .;        else skip types "mypy not installed"; fi
    ;;
  rust)
    run types cargo check --all-targets
    if has cargo-clippy || cargo clippy --version >/dev/null 2>&1; then
      run lint cargo clippy --all-targets -- -D warnings
    else skip lint "clippy not installed"; fi
    ;;
  go)
    run types go vet ./...
    if has golangci-lint; then run lint golangci-lint run; else skip lint "golangci-lint not installed"; fi
    ;;
  *)
    skip types "unknown stack"; skip lint "unknown stack"
    ;;
esac

# ---------------------------------------------------------------------------
# TIER 2 - full. Tests and build. The default gate before any PR.
# ---------------------------------------------------------------------------
if [ "$LEVEL" = "full" ] || [ "$LEVEL" = "deep" ]; then
  case "$STACK" in
    node)
      if pkg_has test; then run test $PMRUN test; else skip test "no test script"; fi
      if pkg_has build; then run build $PMRUN build; else skip build "no build script"; fi
      ;;
    book-to-skill)
      if has pytest; then
        run test bash -c 'set -euo pipefail; pytest tests/ -q; sample_dir="$(mktemp -d)"; printf "# Backpressure\\n\\nChapter 1\\nBounded queues prevent overload.\\n" > "$sample_dir/note.md"; export BOOK_SKILL_WORKDIR="$sample_dir/work"; python3 scripts/extract.py "$sample_dir/note.md" --mode text --install-missing no; test -f "$sample_dir/work/full_text.txt"; test -f "$sample_dir/work/metadata.json"; grep -q "Backpressure" "$sample_dir/work/full_text.txt"; /bin/rm -rf "$sample_dir"'
      else
        skip test "pytest not installed"
      fi
      if has mkdocs; then
        run build mkdocs build
      else
        skip build "mkdocs not installed"
      fi
      ;;
    python)
      if has pytest; then run test pytest -q; else skip test "pytest not installed"; fi
      ;;
    rust)
      run test cargo test --all
      run build cargo build --release
      ;;
    go)
      run test go test ./...
      run build go build ./...
      ;;
    *) skip test "unknown stack"; skip build "unknown stack" ;;
  esac
fi

# ---------------------------------------------------------------------------
# TIER 3 - deep. Security, complexity, mutation, architecture rules.
# Run on anything touching a load-bearing path (see docs/factory/CHARTER.md).
# ---------------------------------------------------------------------------
if [ "$LEVEL" = "deep" ]; then
  case "$STACK" in
    node)
      run audit $PM audit --audit-level=high
      if pkg_has mutation; then run mutation $PMRUN mutation
      else skip mutation "no 'mutation' script (see CHARTER.md - coverage is not a substitute)"; fi
      ;;
    book-to-skill)
      if has bandit; then
        run audit bandit -q -r book_to_skill scripts tools --severity-level high --confidence-level medium
      else
        skip audit "bandit not installed"
      fi
      skip mutation "no repository mutation command"
      ;;
    python)
      if has pip-audit; then run audit pip-audit; else skip audit "pip-audit not installed"; fi
      if has mutmut;    then run mutation mutmut run; else skip mutation "mutmut not installed"; fi
      ;;
    rust)
      if has cargo-audit; then run audit cargo audit; else skip audit "cargo-audit not installed"; fi
      ;;
    go)
      if has govulncheck; then run audit govulncheck ./...; else skip audit "govulncheck not installed"; fi
      ;;
    *)
      skip audit "unknown stack"
      skip mutation "unknown stack"
      ;;
  esac

  # Architecture rules: the project has a real contract validator for its
  # always-loaded SKILL.md. Other stacks fail closed until they add one.
  if [ "$STACK" = "book-to-skill" ]; then
    if has python3; then
      run architecture python3 tools/validate_skill.py SKILL.md
    else
      skip architecture "python3 not installed"
    fi
  else
    skip architecture "no repository-specific architecture validation configured"
  fi
fi

# ---------------------------------------------------------------------------
# VERDICT
# ---------------------------------------------------------------------------
STATUS="GREEN"
EXIT_STATUS=0
if [ -n "$MISCONFIGURED" ]; then
  STATUS="MISCONFIGURED"
  EXIT_STATUS=2
elif [ "$FAILED" -gt 0 ]; then
  STATUS="RED"
  EXIT_STATUS=1
fi

printf '\n---------------------------------------------\n'
[ -n "$SKIPPED" ] && c_dim "skipped: $SKIPPED"
case "$STATUS" in
  GREEN) c_green "GATES GREEN ($PASSED passed)" ;;
  RED) c_red "GATES RED ($FAILED failed: $FAILING)" ;;
  MISCONFIGURED) c_red "GATES MISCONFIGURED (required gates skipped: $MISCONFIGURED)" ;;
esac

# The machine-readable line. Skills are instructed to quote this verbatim and
# are forbidden from reporting a result that contradicts it.
printf 'FACTORY_GATES: level=%s status=%s passed=%d failed=%d failing=%s skipped=%s misconfigured=%s\n' \
  "$LEVEL" "$STATUS" "$PASSED" "$FAILED" "${FAILING:-none}" "${SKIPPED:-none}" "${MISCONFIGURED:-none}"

exit "$EXIT_STATUS"
