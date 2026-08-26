#!/usr/bin/env bash
# Preview or create the labels used as the factory's live queue.

set -euo pipefail

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

command -v gh >/dev/null 2>&1 || {
  echo "error: gh is required to inspect or create factory labels" >&2
  exit 2
}
gh auth status >/dev/null 2>&1 || {
  echo "error: gh is not authenticated" >&2
  exit 2
}

labels=(
  "factory:ready-to-implement|0E8A16|Eligible for one implementation run"
  "factory:ready-to-spec|FBCA04|Needs interactive product or design decisions"
  "factory:needs-info|D93F0B|Blocked on a named question"
  "factory:wait-to-implement|C5DEF5|Understood but blocked on a dependency"
  "factory:in-progress|1D76DB|Claimed by an implementation run"
  "factory:awaiting-review|5319E7|Pull request open; human decision required"
  "factory:verified|0E8A16|Independent verification accepted"
  "factory:rejected|B60205|Independent verification found a blocker"
  "factory:monitor|BFDADC|Filed by the factory monitor"
)

if [ "$APPLY" -eq 0 ]; then
  echo "Would create or update these labels:"
  printf '  %s\n' "${labels[@]%%|*}"
  echo
  echo "Re-run with --apply to write them."
  exit 0
fi

for entry in "${labels[@]}"; do
  IFS='|' read -r name color description <<< "$entry"
  gh label create "$name" --color "$color" --description "$description" --force
done

echo "Factory labels are ready."
