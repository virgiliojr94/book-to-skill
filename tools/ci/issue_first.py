"""Offline evaluator and GitHub Actions adapter for the issue-first PR gate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlsplit

RECEIPT_PREFIX = "<!-- issue-first-receipt:"
RECEIPT_SUFFIX = "-->"

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_IMPL_FIELD_RE = re.compile(r"^\s*implementation\s+issue\s*:\s*(.+?)\s*$", re.IGNORECASE)
_ISSUE_REF_RE = re.compile(r"^#([1-9][0-9]*)$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass(frozen=True)
class EvaluationResult:
    """Result of evaluating a single PR against the issue-first policy."""

    allowed: bool
    reason: str
    category: str
    issue_number: int | None = None
    head_sha: str = ""


def parse_iso8601(value: str | None) -> datetime | None:
    """Parse an ISO-8601 UTC timestamp string into an aware datetime."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_scope_hash(title: str, body: str | None) -> str:
    """Deterministic SHA-256 hash binding an issue's approved title and body."""
    normalized = f"{(title or '').strip()}\n---\n{(body or '').strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _strip_comments_and_fences(text: str) -> str:
    """Remove HTML comments and fenced code blocks before metadata parsing."""
    without_comments = _HTML_COMMENT_RE.sub("", text or "")
    kept_lines: list[str] = []
    fence_char = ""
    fence_len = 0
    for line in without_comments.splitlines():
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            if not fence_char:
                fence_char = marker[0]
                fence_len = len(marker)
                continue
            if marker[0] == fence_char and len(marker) >= fence_len and line.strip() == marker:
                fence_char = ""
                fence_len = 0
                continue
        if not fence_char:
            kept_lines.append(line)
    return "\n".join(kept_lines)


def parse_implementation_issue(body: str | None) -> tuple[int | None, str | None]:
    """Extract a unique `Implementation issue: #<N>` from a PR body.

    Returns `(issue_number, error_reason)`.
    """
    cleaned = _strip_comments_and_fences(body or "")
    matches: list[str] = []
    for line in cleaned.splitlines():
        m = _IMPL_FIELD_RE.match(line)
        if m:
            matches.append(m.group(1).strip())
    if not matches:
        return None, "missing `Implementation issue: #<N>` field in PR description"
    if len(matches) > 1:
        return None, "multiple `Implementation issue:` fields found; specify exactly one"
    ref_match = _ISSUE_REF_RE.match(matches[0])
    if not ref_match:
        return (
            None,
            f"invalid `Implementation issue:` value {matches[0]!r}; expected `#<number>`",
        )
    return int(ref_match.group(1)), None


def format_receipt_comment(
    *,
    issue_number: int,
    actor: str,
    scope_hash: str,
    approved_at: str,
    policy_version: int = 1,
) -> str:
    """Build a structured, auditable approval receipt comment."""
    payload = json.dumps(
        {
            "issue": issue_number,
            "actor": actor,
            "scope_hash": scope_hash,
            "approved_at": approved_at,
            "policy_version": policy_version,
        },
        sort_keys=True,
    )
    return (
        f"Approved for implementation by `@{actor}` (scope `{scope_hash}`).\n\n"
        f"{RECEIPT_PREFIX} {payload} {RECEIPT_SUFFIX}"
    )


def parse_receipt_comment(comment_body: str | None) -> dict[str, Any] | None:
    """Parse a structured receipt comment payload if present and well-formed."""
    if not comment_body:
        return None
    start = comment_body.find(RECEIPT_PREFIX)
    if start < 0:
        return None
    end = comment_body.find(RECEIPT_SUFFIX, start + len(RECEIPT_PREFIX))
    if end < 0:
        return None
    raw = comment_body[start + len(RECEIPT_PREFIX) : end].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _is_verified_dependabot(
    pr: dict[str, Any],
    pr_files: list[str],
    allowed_prefixes: list[str],
) -> tuple[bool, str]:
    """Verify Dependabot identity and restrict modified files to dependency bumps."""
    user = pr.get("user") or {}
    if user.get("login") != "dependabot[bot]" or user.get("type") != "Bot":
        return False, ""
    head_repo = ((pr.get("head") or {}).get("repo") or {}).get("full_name")
    base_repo = ((pr.get("base") or {}).get("repo") or {}).get("full_name")
    if head_repo and base_repo and head_repo != base_repo:
        return False, "Dependabot head repository does not match base repository"
    if not pr_files:
        return False, "Dependabot PR has no file list to verify"
    disallowed = [
        path for path in pr_files
        if not any(path.startswith(prefix) for prefix in allowed_prefixes)
    ]
    if disallowed:
        return (
            False,
            f"Dependabot exception denied: disallowed files modified ({', '.join(disallowed[:3])})",
        )
    return True, "verified Dependabot dependency update"


def evaluate_pr(
    *,
    pr: dict[str, Any],
    pr_files: list[str],
    policy: dict[str, Any],
    issue: dict[str, Any] | None = None,
    issue_events: list[dict[str, Any]] | None = None,
    issue_comments: list[dict[str, Any]] | None = None,
) -> EvaluationResult:
    """Evaluate PR eligibility against the issue-first policy cleanly and offline."""
    pr_number = int(pr["number"])
    head_sha = str((pr.get("head") or {}).get("sha") or "")

    # 1. Frozen legacy PRs opened before policy activation.
    if pr_number in set(int(n) for n in policy.get("legacy_prs", [])):
        return EvaluationResult(
            allowed=True,
            reason=f"PR #{pr_number} is on the frozen legacy policy list",
            category="legacy",
            head_sha=head_sha,
        )

    # 2. Private security SHA-pinned exception authorized by a maintainer.
    sec_entry = (policy.get("private_security_exceptions") or {}).get(str(pr_number))
    if isinstance(sec_entry, dict):
        maintainers = set(policy.get("maintainers", []))
        auth_by = sec_entry.get("authorized_by")
        pinned_sha = sec_entry.get("head_sha")
        if auth_by in maintainers and pinned_sha and head_sha == pinned_sha:
            return EvaluationResult(
                allowed=True,
                reason=f"Authorized private security fix at {head_sha[:7]}",
                category="private_security",
                head_sha=head_sha,
            )
        return EvaluationResult(
            allowed=False,
            reason=(
                f"Private security exception for PR #{pr_number} does not match "
                f"current head SHA {head_sha[:7]}"
            ),
            category="private_security_mismatch",
            head_sha=head_sha,
        )

    # 3. Verified Dependabot dependency/workflow updates.
    user = pr.get("user") or {}
    if user.get("login") == "dependabot[bot]":
        ok, dep_reason = _is_verified_dependabot(
            pr,
            pr_files,
            list(policy.get("dependabot_allowed_prefixes", [])),
        )
        return EvaluationResult(
            allowed=ok,
            reason=dep_reason,
            category="dependabot" if ok else "dependabot_rejected",
            head_sha=head_sha,
        )

    # 4. Normal PRs (including maintainer and docs PRs) require an approved issue.
    issue_num, parse_err = parse_implementation_issue(pr.get("body"))
    if parse_err or issue_num is None:
        return EvaluationResult(
            allowed=False,
            reason=parse_err or "Missing Implementation issue field",
            category="missing_or_invalid_field",
            head_sha=head_sha,
        )

    if issue is None:
        return EvaluationResult(
            allowed=False,
            reason=f"Referenced issue #{issue_num} was not found",
            category="issue_not_found",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    if "pull_request" in issue:
        return EvaluationResult(
            allowed=False,
            reason=f"#{issue_num} is a pull request, not an issue",
            category="not_an_issue",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    if issue.get("state") != "open":
        return EvaluationResult(
            allowed=False,
            reason=f"Issue #{issue_num} is {issue.get('state')}, expected open",
            category="issue_closed",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    approval_label = str(policy.get("approval_label", "approved-for-implementation"))
    maintainers = set(policy.get("maintainers", []))
    label_names = {
        str((lbl or {}).get("name") or "")
        for lbl in (issue.get("labels") or [])
    }
    if approval_label not in label_names:
        return EvaluationResult(
            allowed=False,
            reason=f"Issue #{issue_num} does not carry `{approval_label}`",
            category="missing_approval_label",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    # Verify label chronology and actor identity via timeline/events.
    pr_created_at = parse_iso8601(pr.get("created_at"))
    if pr_created_at is None:
        return EvaluationResult(
            allowed=False,
            reason="PR creation timestamp is missing or invalid",
            category="invalid_pr_timestamp",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    earliest_valid_approval: datetime | None = None
    active_maintainer_label = False
    latest_label_event_at: datetime | None = None

    sorted_events = sorted(
        (issue_events or []),
        key=lambda ev: parse_iso8601(ev.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
    )
    for ev in sorted_events:
        ev_type = ev.get("event")
        ev_time = parse_iso8601(ev.get("created_at"))
        actor = str(((ev.get("actor") or {}).get("login")) or "")
        lbl_name = str(((ev.get("label") or {}).get("name")) or "")
        if ev_type == "labeled" and lbl_name == approval_label:
            if actor in maintainers and ev_time is not None:
                active_maintainer_label = True
                latest_label_event_at = ev_time
                if earliest_valid_approval is None or ev_time < earliest_valid_approval:
                    earliest_valid_approval = ev_time
            else:
                active_maintainer_label = False
        elif ev_type == "unlabeled" and lbl_name == approval_label:
            active_maintainer_label = False
        elif ev_type in ("closed", "transferred"):
            active_maintainer_label = False

    if not active_maintainer_label or earliest_valid_approval is None or latest_label_event_at is None:
        return EvaluationResult(
            allowed=False,
            reason=(
                f"Issue #{issue_num} lacks an active `{approval_label}` event "
                f"by an authorized maintainer"
            ),
            category="unverified_approval_actor",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    if earliest_valid_approval > pr_created_at:
        return EvaluationResult(
            allowed=False,
            reason=(
                f"Issue #{issue_num} was approved after PR #{pr_number} was opened; "
                "approval must precede PR creation"
            ),
            category="approved_after_pr_created",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    # Verify scope receipt hash against the current issue title and body.
    current_hash = compute_scope_hash(
        str(issue.get("title") or ""),
        issue.get("body"),
    )
    trusted_authors = set(policy.get("trusted_receipt_authors", [])) | maintainers
    latest_receipt: dict[str, Any] | None = None
    latest_receipt_time: datetime | None = None
    for comment in issue_comments or []:
        author = str(((comment.get("user") or {}).get("login")) or "")
        if author not in trusted_authors:
            continue
        parsed = parse_receipt_comment(comment.get("body"))
        if not parsed:
            continue
        if parsed.get("issue") != issue_num or parsed.get("actor") not in maintainers:
            continue
        c_time = parse_iso8601(comment.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if latest_receipt_time is None or c_time >= latest_receipt_time:
            latest_receipt_time = c_time
            latest_receipt = parsed

    if latest_receipt is None:
        return EvaluationResult(
            allowed=False,
            reason=f"Issue #{issue_num} is missing a verified scope-approval receipt",
            category="missing_receipt",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    if latest_receipt.get("scope_hash") != current_hash:
        return EvaluationResult(
            allowed=False,
            reason=(
                f"Issue #{issue_num} scope changed after approval "
                f"(receipt {latest_receipt.get('scope_hash')} != current {current_hash}); "
                "maintainer re-approval required"
            ),
            category="scope_hash_mismatch",
            issue_number=issue_num,
            head_sha=head_sha,
        )

    return EvaluationResult(
        allowed=True,
        reason=f"Linked to approved issue #{issue_num} (scope `{current_hash}`)",
        category="approved",
        issue_number=issue_num,
        head_sha=head_sha,
    )


def _github_api_request(
    method: str,
    path_or_url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, str], Any]:
    """Issue a strict HTTPS call to api.github.com only."""
    if path_or_url.startswith("https://"):
        split = urlsplit(path_or_url)
        if split.hostname != "api.github.com":
            raise ValueError(f"Refusing non-GitHub API host: {split.hostname}")
        path = split.path + (f"?{split.query}" if split.query else "")
    else:
        path = path_or_url

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "book-to-skill-issue-first-ci",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body_bytes: bytes | None = None
    if payload is not None:
        body_bytes = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    conn = http.client.HTTPSConnection("api.github.com", timeout=20)
    try:
        conn.request(method, path, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        parsed = json.loads(raw) if raw.strip() else None
        return resp.status, resp_headers, parsed
    finally:
        conn.close()


def _parse_next_link(link_header: str) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            m = re.search(r"<(https://api\.github\.com/[^>]+)>", part)
            if m:
                return m.group(1)
    return None


def fetch_paginated(path: str, token: str, *, max_pages: int = 20) -> list[dict[str, Any]]:
    """Fetch all paginated GitHub API items, raising on errors or truncation."""
    sep = "&" if "?" in path else "?"
    next_url: str | None = f"{path}{sep}per_page=100"
    items: list[dict[str, Any]] = []
    pages = 0
    while next_url:
        pages += 1
        if pages > max_pages:
            raise RuntimeError(f"Pagination exceeded {max_pages} pages for {path}")
        status, headers, data = _github_api_request("GET", next_url, token)
        if status >= 400 or not isinstance(data, list):
            raise RuntimeError(f"GitHub API error {status} fetching {next_url}: {data}")
        items.extend(data)
        next_url = _parse_next_link(headers.get("link", ""))
    return items


def fetch_single(path: str, token: str) -> dict[str, Any] | None:
    """Fetch a single GitHub API resource (returns None only on HTTP 404)."""
    status, _headers, data = _github_api_request("GET", path, token)
    if status == 404:
        return None
    if status >= 400 or not isinstance(data, dict):
        raise RuntimeError(f"GitHub API error {status} fetching {path}: {data}")
    return data


def post_commit_status(
    *,
    repo: str,
    sha: str,
    context: str,
    state: str,
    description: str,
    token: str,
) -> None:
    """Publish commit status context on the PR head SHA."""
    desc = description[:137] + "..." if len(description) > 140 else description
    status, _headers, data = _github_api_request(
        "POST",
        f"/repos/{repo}/statuses/{sha}",
        token,
        {"state": state, "context": context, "description": desc},
    )
    if status >= 400:
        raise RuntimeError(f"Failed to publish commit status ({status}): {data}")


def evaluate_remote_pr(
    *,
    repo: str,
    pr_number: int,
    policy: dict[str, Any],
    token: str,
    publish_status: bool = True,
) -> EvaluationResult:
    """Fetch live PR/issue data from GitHub API and evaluate."""
    pr = fetch_single(f"/repos/{repo}/pulls/{pr_number}", token)
    if pr is None:
        raise RuntimeError(f"PR #{pr_number} not found in {repo}")
    pr_files = [
        str(f.get("filename") or "")
        for f in fetch_paginated(f"/repos/{repo}/pulls/{pr_number}/files", token)
    ]

    issue_num, _ = parse_implementation_issue(pr.get("body"))
    issue = None
    events: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    if issue_num is not None:
        issue = fetch_single(f"/repos/{repo}/issues/{issue_num}", token)
        if issue is not None and "pull_request" not in issue:
            events = fetch_paginated(f"/repos/{repo}/issues/{issue_num}/events", token)
            comments = fetch_paginated(f"/repos/{repo}/issues/{issue_num}/comments", token)

    result = evaluate_pr(
        pr=pr,
        pr_files=pr_files,
        policy=policy,
        issue=issue,
        issue_events=events,
        issue_comments=comments,
    )
    if publish_status and result.head_sha:
        # Re-read PR head SHA before writing status so stale runs never stamp newer commits.
        fresh_pr = fetch_single(f"/repos/{repo}/pulls/{pr_number}", token)
        fresh_sha = str(((fresh_pr or {}).get("head") or {}).get("sha") or "")
        if fresh_sha != result.head_sha:
            raise RuntimeError(
                f"Head SHA changed during evaluation ({result.head_sha[:7]} -> {fresh_sha[:7]})"
            )
        post_commit_status(
            repo=repo,
            sha=result.head_sha,
            context=str(policy.get("status_context", "issue-first / approved-issue")),
            state="success" if result.allowed else "failure",
            description=result.reason,
            token=token,
        )
    return result


def reconcile_issue_receipt(
    *,
    repo: str,
    issue_number: int,
    policy: dict[str, Any],
    token: str,
) -> bool:
    """Post an approval receipt comment when a maintainer labels an issue."""
    issue = fetch_single(f"/repos/{repo}/issues/{issue_number}", token)
    if issue is None or "pull_request" in issue or issue.get("state") != "open":
        return False

    approval_label = str(policy.get("approval_label", "approved-for-implementation"))
    maintainers = set(policy.get("maintainers", []))
    label_names = {str((lbl or {}).get("name") or "") for lbl in (issue.get("labels") or [])}
    if approval_label not in label_names:
        return False

    events = fetch_paginated(f"/repos/{repo}/issues/{issue_number}/events", token)
    latest_actor: str | None = None
    latest_time: str | None = None
    for ev in sorted(
        events,
        key=lambda e: parse_iso8601(e.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
    ):
        lbl = str(((ev.get("label") or {}).get("name")) or "")
        if ev.get("event") == "labeled" and lbl == approval_label:
            actor = str(((ev.get("actor") or {}).get("login")) or "")
            if actor in maintainers:
                latest_actor = actor
                latest_time = str(ev.get("created_at") or "")
            else:
                latest_actor = None
        elif ev.get("event") == "unlabeled" and lbl == approval_label:
            latest_actor = None

    if not latest_actor:
        return False

    current_hash = compute_scope_hash(str(issue.get("title") or ""), issue.get("body"))
    comments = fetch_paginated(f"/repos/{repo}/issues/{issue_number}/comments", token)
    trusted = set(policy.get("trusted_receipt_authors", [])) | maintainers
    for c in comments:
        if str(((c.get("user") or {}).get("login")) or "") not in trusted:
            continue
        parsed = parse_receipt_comment(c.get("body"))
        if (
            parsed
            and parsed.get("issue") == issue_number
            and parsed.get("actor") == latest_actor
            and parsed.get("scope_hash") == current_hash
        ):
            return False

    body = format_receipt_comment(
        issue_number=issue_number,
        actor=latest_actor,
        scope_hash=current_hash,
        approved_at=latest_time or datetime.now(timezone.utc).isoformat(),
        policy_version=int(policy.get("policy_version", 1)),
    )
    status, _h, data = _github_api_request(
        "POST",
        f"/repos/{repo}/issues/{issue_number}/comments",
        token,
        {"body": body},
    )
    if status >= 400:
        raise RuntimeError(f"Failed to post receipt comment ({status}): {data}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue-first PR eligibility gate")
    parser.add_argument("--policy", default=".github/issue-first-policy.json")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr", type=int, default=None)
    parser.add_argument("--issue", type=int, default=None)
    parser.add_argument("--publish-status", action="store_true")
    parser.add_argument("--reconcile-prs", action="store_true")
    args = parser.parse_args(argv)

    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or not args.repo:
        print("GITHUB_TOKEN and --repo are required", file=sys.stderr)
        return 2

    mode = policy.get("mode", "observe")
    if args.issue is not None:
        reconcile_issue_receipt(
            repo=args.repo,
            issue_number=args.issue,
            policy=policy,
            token=token,
        )
        if args.reconcile_prs:
            open_prs = fetch_paginated(f"/repos/{args.repo}/pulls?state=open", token)
            for pr in open_prs:
                ref, _ = parse_implementation_issue(pr.get("body"))
                if ref == args.issue:
                    evaluate_remote_pr(
                        repo=args.repo,
                        pr_number=int(pr["number"]),
                        policy=policy,
                        token=token,
                        publish_status=args.publish_status,
                    )
        return 0

    if args.pr is not None:
        res = evaluate_remote_pr(
            repo=args.repo,
            pr_number=args.pr,
            policy=policy,
            token=token,
            publish_status=args.publish_status,
        )
        print(f"PR #{args.pr}: allowed={res.allowed} ({res.category}) — {res.reason}")
        if not res.allowed and mode == "enforce":
            return 1
        return 0

    open_prs = fetch_paginated(f"/repos/{args.repo}/pulls?state=open", token)
    blocked = 0
    for pr in open_prs:
        res = evaluate_remote_pr(
            repo=args.repo,
            pr_number=int(pr["number"]),
            policy=policy,
            token=token,
            publish_status=args.publish_status,
        )
        print(f"PR #{pr['number']}: allowed={res.allowed} ({res.category}) — {res.reason}")
        if not res.allowed:
            blocked += 1
    if blocked and mode == "enforce":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
