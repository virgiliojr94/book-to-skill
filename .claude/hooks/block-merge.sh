#!/usr/bin/env bash
# block-merge.sh - defense-in-depth checks for factory shell commands.
#
# This catches common shell routes to merging or bypassing factory policy. It is
# not the enforcement boundary: tool hooks cannot cover every hosted/API path.
# Protect the default branch with a GitHub ruleset and do not grant agents bypass.
#
# Wired as a PreToolUse hook on Bash in .claude/settings.json.
# Reads the tool call as JSON on stdin. Exit 2 blocks the call and returns
# stderr to the agent as feedback.

set -uo pipefail

INPUT="$(cat)"

# Extract the command without requiring jq (cloud sessions have jq, but a
# local machine might not, and this hook must never be the thing that breaks).
if command -v jq >/dev/null 2>&1; then
  CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"
else
  CMD="$(printf '%s' "$INPUT" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p')"
fi

[ -z "$CMD" ] && exit 0

block() {
  echo "BLOCKED by factory hook: $1" >&2
  echo "" >&2
  echo "The merge decision belongs to a human. See docs/factory/CHARTER.md." >&2
  echo "Open a PR and stop; do not attempt an alternative route to merging." >&2
  exit 2
}

# Merging, in every spelling.
case "$CMD" in
  *"gh pr merge"*)          block "gh pr merge" ;;
  *"mergePullRequest"*)     block "GitHub merge API" ;;
  *"/pulls/"*"/merge"*)    block "GitHub merge API" ;;
  *"git merge "*)           block "git merge" ;;
  *"git push --force"*)     block "force push" ;;
  *"git push -f"*)          block "force push" ;;
esac

# Direct pushes to common protected branches. Repository rulesets must cover the
# real default branch if it uses another name.
if printf '%s' "$CMD" | grep -qE '(^|[;&|[:space:]])git[[:space:]]+push'; then
  if printf '%s' "$CMD" | grep -qE 'push([^;&|]*[[:space:]])(\+?refs/heads/|\+?HEAD:(refs/heads/)?)?(main|master|develop|production)([[:space:]]|$)'; then
    block "push to a protected branch"
  fi
  current_branch="$(git branch --show-current 2>/dev/null || true)"
  if printf '%s' "$CMD" | grep -qE 'git[[:space:]]+push([[:space:]]+\S+)?[[:space:]]*$' && \
     printf '%s' "$current_branch" | grep -qE '^(main|master|develop|production)$'; then
    block "push from a protected branch"
  fi
fi

# Editing the charter or the gate script through the shell, which would otherwise
# route around the Edit deny rules in settings.json.
if printf '%s' "$CMD" | grep -qE '(docs/factory/CHARTER\.md|\.factory/gates\.conf|\.claude/|\.agents/|\.codex/)'; then
  if printf '%s' "$CMD" | grep -qE '(^|[;&|[:space:]])(sed|tee|cat[[:space:]]*>|>|>>|rm|mv|cp|truncate)'; then
    block "writing to a protected factory file via the shell"
  fi
fi

exit 0
