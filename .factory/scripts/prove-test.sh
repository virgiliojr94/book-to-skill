#!/usr/bin/env bash
# Prove that a test fails when the non-test portion of a committed change is removed.
# The working tree must be clean. The script restores it even when the test command fails.
#
# Usage:
#   ./.factory/scripts/prove-test.sh <base-ref> --test-path <path> -- <test command...>

set -euo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
  echo "usage: $0 <base-ref> [--test-path <path>]... -- <test command...>" >&2
  exit 2
fi
shift

test_paths=()
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
  if [ "$1" != "--test-path" ] || [ "$#" -lt 2 ]; then
    echo "usage: $0 <base-ref> [--test-path <path>]... -- <test command...>" >&2
    exit 2
  fi
  test_paths+=("$2")
  shift 2
done

if [ "${1:-}" != "--" ] || [ "$#" -lt 2 ]; then
  echo "usage: $0 <base-ref> [--test-path <path>]... -- <test command...>" >&2
  exit 2
fi
shift

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "PROOF: status=MISCONFIGURED reason=not-a-git-repository" >&2
  exit 2
}
cd "$ROOT"

git rev-parse --verify "$BASE^{commit}" >/dev/null 2>&1 || {
  echo "PROOF: status=MISCONFIGURED reason=invalid-base-ref base=$BASE" >&2
  exit 2
}

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "PROOF: status=MISCONFIGURED reason=working-tree-not-clean" >&2
  exit 2
fi

patch_file="$(mktemp "${TMPDIR:-/tmp}/factory-proof.XXXXXX.patch")"
reverted=0

restore() {
  if [ "$reverted" -eq 1 ] && [ -s "$patch_file" ]; then
    git apply "$patch_file" >/dev/null 2>&1 || {
      echo "PROOF: restore failed; patch retained at $patch_file" >&2
      return
    }
  fi
  rm -f "$patch_file"
}
trap restore EXIT INT TERM

non_test_files=()
while IFS= read -r -d '' path; do
  is_test=0
  for test_path in "${test_paths[@]}"; do
    if [ "$path" = "$test_path" ] || [[ "$path" == "$test_path"/* ]]; then
      is_test=1
      break
    fi
  done
  if [ "${#test_paths[@]}" -eq 0 ]; then
    case "$path" in
      test/*|tests/*|*/test/*|*/tests/*|*/__tests__/*|*.test.*|*.spec.*|test_*|*_test.*|spec_*|*_spec.*) is_test=1 ;;
    esac
  fi
  [ "$is_test" -eq 1 ] || non_test_files+=("$path")
done < <(git diff --name-only -z "$BASE"...HEAD)

if [ "${#non_test_files[@]}" -eq 0 ]; then
  echo "PROOF: status=MISCONFIGURED reason=no-non-test-change" >&2
  exit 2
fi

git diff --binary "$BASE"...HEAD -- "${non_test_files[@]}" > "$patch_file"
if [ ! -s "$patch_file" ]; then
  echo "PROOF: status=MISCONFIGURED reason=empty-revert-patch" >&2
  exit 2
fi

git apply -R "$patch_file"
reverted=1

set +e
"$@"
test_status=$?
set -e

git apply "$patch_file"
reverted=0

if [ "$test_status" -eq 0 ]; then
  echo "PROOF: status=FAILED reason=test-passed-without-fix"
  exit 1
fi

echo "PROOF: status=PROVEN test_exit=$test_status"
