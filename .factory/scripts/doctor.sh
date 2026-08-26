#!/usr/bin/env bash
# Check whether the installed factory has enough configuration to run safely.

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 2

failures=0
warnings=0

pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

required_files=(
  CLAUDE.md
  AGENTS.md
  docs/factory/CONTRACT.md
  docs/factory/CHARTER.md
  .factory/gates.conf
  .claude/scripts/gates.sh
)

for path in "${required_files[@]}"; do
  [ -f "$path" ] && pass "$path exists" || fail "$path is missing"
done

if [ -f CLAUDE.md ] && grep -q '<PROJECT NAME>\|<install>\|<One paragraph:' CLAUDE.md; then
  fail "CLAUDE.md still contains setup placeholders"
else
  pass "CLAUDE.md placeholders replaced"
fi

if [ -f docs/factory/CHARTER.md ] && grep -q '^CHARTER_STATUS: ready$' docs/factory/CHARTER.md; then
  pass "charter is marked ready"
else
  fail "charter is not marked ready"
fi

if [ -f docs/factory/CHARTER.md ] && grep -q '^TIER: \(revival\|greenfield\|oss\|client-production\)$' docs/factory/CHARTER.md; then
  pass "charter tier is valid"
else
  fail "charter tier is missing or invalid"
fi

if git rev-parse --git-dir >/dev/null 2>&1; then
  pass "Git repository detected"
  if git remote get-url origin >/dev/null 2>&1; then pass "origin remote detected"; else warn "no origin remote"; fi
else
  fail "not a Git repository"
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  pass "GitHub CLI authenticated"
  missing_labels=0
  for label in factory:ready-to-implement factory:ready-to-spec factory:needs-info factory:wait-to-implement factory:in-progress factory:awaiting-review; do
    gh label view "$label" >/dev/null 2>&1 || missing_labels=$((missing_labels + 1))
  done
  [ "$missing_labels" -eq 0 ] && pass "live queue labels exist" || warn "$missing_labels live queue labels missing; run ./.factory/scripts/bootstrap-github.sh --apply"
else
  warn "gh is unavailable or unauthenticated; live queue checks skipped"
fi

if [ -f .codex/hooks.json ]; then
  warn "Codex users must review and trust repo hooks with /hooks"
fi
warn "verify GitHub branch protection or a ruleset manually; see docs/factory/GITHUB.md"

printf '\nFACTORY_DOCTOR: failures=%d warnings=%d\n' "$failures" "$warnings"
[ "$failures" -eq 0 ]
