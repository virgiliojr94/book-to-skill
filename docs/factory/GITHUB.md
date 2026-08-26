# GitHub setup

GitHub carries the factory's live queue and its merge boundary. This page records the
repository-side setup that cannot be inferred safely from Markdown alone.

## Queue labels

Preview and create the labels:

```bash
./.factory/scripts/bootstrap-github.sh
./.factory/scripts/bootstrap-github.sh --apply
```

Queue-state labels are mutually exclusive. `factory:monitor` is provenance and may coexist
with one issue state. `factory:verified` and `factory:rejected` belong on pull requests.

## Default-branch rules

Create a GitHub ruleset or branch-protection rule for the actual default branch. At
minimum:

- require changes to arrive through a pull request
- block force pushes and branch deletion
- do not grant the account used by unattended agents a bypass
- require the repository's CI checks once they exist

Whether you require human approvals depends on the repository tier and team. The factory
itself never approves or merges, even when GitHub would permit it.

The committed Claude and Codex hooks block common shell routes to merging and direct
pushes. They cannot cover every hosted tool or API path, so a repository-side rule remains
the enforcement boundary.

## Claim branches

Implementation runs claim work through `claude/fq-<issue-number>`. The first run pushes a
unique empty claim commit without force. A later run starts from the same base with a
different claim commit, so Git rejects its non-fast-forward push.

If a claim is stale, inspect the issue, branch, cloud session, and latest run record. A
human may then delete or recover the branch. Monitoring reports stale claims but never
steals them automatically.
