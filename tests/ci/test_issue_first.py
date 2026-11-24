"""Deterministic offline tests for tools/ci/issue_first.py."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import issue_first  # noqa: E402


def _policy(**overrides):
    base = {
        "policy_version": 1,
        "mode": "observe",
        "status_context": "issue-first / approved-issue",
        "maintainers": ["virgiliojr94"],
        "approval_label": "approved-for-implementation",
        "trusted_receipt_authors": ["virgiliojr94", "github-actions[bot]"],
        "legacy_prs": [129, 345],
        "dependabot_allowed_prefixes": [".github/workflows/", "pyproject.toml"],
        "private_security_exceptions": {},
    }
    base.update(overrides)
    return base


def _issue(*, number=360, state="open", title="Approved bug", body="Repro + scope", labeled=True):
    return {
        "number": number,
        "state": state,
        "title": title,
        "body": body,
        "labels": [{"name": "approved-for-implementation"}] if labeled else [],
    }


def _receipt(*, issue_num=360, title="Approved bug", body="Repro + scope", actor="virgiliojr94", author="github-actions[bot]", created_at="2026-11-24T10:01:00Z"):
    scope_hash = issue_first.compute_scope_hash(title, body)
    return {
        "user": {"login": author},
        "created_at": created_at,
        "body": issue_first.format_receipt_comment(
            issue_number=issue_num,
            actor=actor,
            scope_hash=scope_hash,
            approved_at="2026-11-24T10:00:00Z",
        ),
    }


def _events(*, actor="virgiliojr94", created_at="2026-11-24T10:00:00Z", label="approved-for-implementation"):
    return [
        {
            "event": "labeled",
            "created_at": created_at,
            "actor": {"login": actor},
            "label": {"name": label},
        }
    ]


def _pr(*, number=400, login="contrib", user_type="User", created_at="2026-11-24T12:00:00Z", body="Implementation issue: #360\n", sha="abc1234", head_repo=None):
    return {
        "number": number,
        "created_at": created_at,
        "user": {"login": login, "type": user_type},
        "head": {"sha": sha, "repo": {"full_name": head_repo or f"{login}/book-to-skill"}},
        "base": {"repo": {"full_name": "virgiliojr94/book-to-skill"}},
        "body": body,
    }


def test_parse_implementation_issue_rejects_comments_fences_na_and_duplicates():
    assert issue_first.parse_implementation_issue("<!-- Implementation issue: #1 -->")[0] is None
    assert issue_first.parse_implementation_issue("```text\nImplementation issue: #1\n```")[0] is None
    assert issue_first.parse_implementation_issue("Implementation issue: n/a")[0] is None
    assert issue_first.parse_implementation_issue("Implementation issue: owner/repo#12")[0] is None
    assert issue_first.parse_implementation_issue("Implementation issue: #1\nImplementation issue: #2")[0] is None
    num, err = issue_first.parse_implementation_issue("## Motivation\nImplementation issue: #360\n")
    assert num == 360 and err is None


def test_approved_issue_before_pr_passes_even_for_maintainer():
    res = issue_first.evaluate_pr(
        pr=_pr(login="virgiliojr94"),
        pr_files=["book_to_skill/utils.py"],
        policy=_policy(),
        issue=_issue(),
        issue_events=_events(),
        issue_comments=[_receipt()],
    )
    assert res.allowed is True
    assert res.category == "approved"
    assert res.issue_number == 360


def test_maintainer_and_small_doc_prs_still_require_approved_issue():
    res = issue_first.evaluate_pr(
        pr=_pr(login="virgiliojr94", body="## Summary\nTiny doc tweak\nCloses #n/a"),
        pr_files=["README.md"],
        policy=_policy(),
    )
    assert res.allowed is False
    assert res.category == "missing_or_invalid_field"


def test_pr_pointing_to_another_pr_or_closed_issue_is_rejected():
    as_pr = _issue()
    as_pr["pull_request"] = {"url": "https://api.github.com/repos/x/y/pulls/360"}
    assert issue_first.evaluate_pr(
        pr=_pr(), pr_files=["a.py"], policy=_policy(), issue=as_pr,
        issue_events=_events(), issue_comments=[_receipt()],
    ).category == "not_an_issue"

    closed = _issue(state="closed")
    assert issue_first.evaluate_pr(
        pr=_pr(), pr_files=["a.py"], policy=_policy(), issue=closed,
        issue_events=_events(), issue_comments=[_receipt()],
    ).category == "issue_closed"


def test_forged_receipt_or_non_maintainer_label_is_rejected():
    res_bad_actor = issue_first.evaluate_pr(
        pr=_pr(),
        pr_files=["a.py"],
        policy=_policy(),
        issue=_issue(),
        issue_events=_events(actor="triage-helper"),
        issue_comments=[_receipt()],
    )
    assert res_bad_actor.allowed is False
    assert res_bad_actor.category == "unverified_approval_actor"

    res_forged_receipt = issue_first.evaluate_pr(
        pr=_pr(),
        pr_files=["a.py"],
        policy=_policy(),
        issue=_issue(),
        issue_events=_events(),
        issue_comments=[_receipt(author="random-user")],
    )
    assert res_forged_receipt.allowed is False
    assert res_forged_receipt.category == "missing_receipt"


def test_scope_edit_revokes_approval_until_reapproved_but_keeps_early_pr_eligible():
    edited_issue = _issue(body="Repro + expanded extra scope")
    revoked = issue_first.evaluate_pr(
        pr=_pr(created_at="2026-11-24T12:00:00Z"),
        pr_files=["a.py"],
        policy=_policy(),
        issue=edited_issue,
        issue_events=_events(created_at="2026-11-24T10:00:00Z"),
        issue_comments=[_receipt()],
    )
    assert revoked.allowed is False
    assert revoked.category == "scope_hash_mismatch"

    # Re-approved later while original approval preceded PR creation -> eligible again.
    events = _events(created_at="2026-11-24T10:00:00Z") + _events(created_at="2026-11-24T13:00:00Z")
    comments = [_receipt(), _receipt(body="Repro + expanded extra scope", created_at="2026-11-24T13:01:00Z")]
    reapproved = issue_first.evaluate_pr(
        pr=_pr(created_at="2026-11-24T12:00:00Z"),
        pr_files=["a.py"],
        policy=_policy(),
        issue=edited_issue,
        issue_events=events,
        issue_comments=comments,
    )
    assert reapproved.allowed is True


def test_approval_after_pr_creation_is_rejected():
    res = issue_first.evaluate_pr(
        pr=_pr(created_at="2026-11-24T09:00:00Z"),
        pr_files=["a.py"],
        policy=_policy(),
        issue=_issue(),
        issue_events=_events(created_at="2026-11-24T10:00:00Z"),
        issue_comments=[_receipt()],
    )
    assert res.allowed is False
    assert res.category == "approved_after_pr_created"


def test_exceptions_legacy_dependabot_and_private_security():
    legacy = issue_first.evaluate_pr(pr=_pr(number=345, body="old"), pr_files=[], policy=_policy())
    assert legacy.allowed is True and legacy.category == "legacy"

    dep_ok = issue_first.evaluate_pr(
        pr=_pr(login="dependabot[bot]", user_type="Bot", body="bump", head_repo="virgiliojr94/book-to-skill"),
        pr_files=[".github/workflows/ci.yml"],
        policy=_policy(),
    )
    assert dep_ok.allowed is True and dep_ok.category == "dependabot"

    dep_bad_repo = issue_first.evaluate_pr(
        pr=_pr(login="dependabot[bot]", user_type="Bot", body="bump", head_repo="attacker/book-to-skill"),
        pr_files=[".github/workflows/ci.yml"],
        policy=_policy(),
    )
    assert dep_bad_repo.allowed is False and dep_bad_repo.category == "dependabot_rejected"

    dep_bad_file = issue_first.evaluate_pr(
        pr=_pr(login="dependabot[bot]", user_type="Bot", body="bump"),
        pr_files=["book_to_skill/utils.py"],
        policy=_policy(),
    )
    assert dep_bad_file.allowed is False and dep_bad_file.category == "dependabot_rejected"

    policy_sec = _policy(
        private_security_exceptions={"401": {"head_sha": "deadbeef", "authorized_by": "virgiliojr94"}}
    )
    assert issue_first.evaluate_pr(
        pr=_pr(number=401, sha="deadbeef", body="security fix"),
        pr_files=["book_to_skill/archive.py"],
        policy=policy_sec,
    ).allowed is True
    assert issue_first.evaluate_pr(
        pr=_pr(number=401, sha="cafebabe", body="security fix"),
        pr_files=["book_to_skill/archive.py"],
        policy=policy_sec,
    ).allowed is False


def test_stale_sha_check_prevents_status_overwrite():
    with mock.patch.object(
        issue_first,
        "fetch_single",
        side_effect=[_pr(number=400, sha="sha_old"), _issue(), _pr(number=400, sha="sha_new")],
    ), mock.patch.object(
        issue_first,
        "fetch_paginated",
        side_effect=[[{"filename": "a.py"}], _events(), [_receipt()]],
    ), mock.patch.object(issue_first, "post_commit_status") as post:
        with pytest.raises(RuntimeError, match="Head SHA changed"):
            issue_first.evaluate_remote_pr(
                repo="virgiliojr94/book-to-skill",
                pr_number=400,
                policy=_policy(),
                token="tok",
                publish_status=True,
            )
        post.assert_not_called()


def test_checked_in_policy_json_is_valid():
    policy = json.loads((ROOT / ".github" / "issue-first-policy.json").read_text(encoding="utf-8"))
    assert policy["maintainers"] == ["virgiliojr94"]
    assert policy["mode"] == "observe"
    assert policy["governance_issue"] == 360
