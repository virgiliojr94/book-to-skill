# Factory operating guide

This directory is the durable operating state for the repository's software factory. Start
here after installing the template into a project.

The first safe milestone is modest: the charter describes the project accurately, the
required gates run locally, and both Claude Code and Codex can report what they would do
without writing anything.

## Configure once

1. Review [CHARTER.md](CHARTER.md). Choose one tier, replace the example paths and work
   categories, set the review-queue limit, and leave `CHARTER_STATUS` as `incomplete` until
   every section has been read.
2. Configure `../../.factory/gates.conf`, then run:

   ```bash
   ./.claude/scripts/gates.sh fast
   ./.claude/scripts/gates.sh full
   ```

3. Replace the project placeholders and command examples at the top of
   [`CLAUDE.md`](../../CLAUDE.md).
4. Preview the GitHub labels with `./.factory/scripts/bootstrap-github.sh`. Add `--apply`
   only after confirming the target repository.
5. Configure branch protection or a GitHub ruleset using [GITHUB.md](GITHUB.md).
6. Run `./.factory/scripts/doctor.sh`, review the installation diff, commit, and push.

Cloud sessions start from the remote repository. An unpushed factory does not exist from
their point of view.

## Use it from Claude Code

The installed project commands are:

- `/factory` reports the live queue, gate health, and work needing human judgment.
- `/factory-tune` reviews evidence and proposes constraint changes.
- `factory-triage`, `factory-spec`, `factory-implement`, `factory-verify`, and
  `factory-monitor` are the workflow skills.

Begin with a report-only triage request:

```text
Run the factory-triage skill in report-only mode. Do not write files or apply labels.
Explain every proposed disposition using the charter.
```

## Use it from Codex

Codex reads [`AGENTS.md`](../../AGENTS.md) and discovers the adapters under
`../../.agents/skills/`. Ask for the workflow by name:

```text
Use the factory-status skill to show the control room. Report only; change nothing.
```

The adapters point to the canonical workflows under `.claude/skills/`. If a Codex adapter
and [CONTRACT.md](CONTRACT.md) disagree, the contract wins.

## Which file owns what?

| File | Role |
|---|---|
| [CHARTER.md](CHARTER.md) | Human-owned risk, scope, autonomy, and stop decisions |
| [CONTRACT.md](CONTRACT.md) | Shared rules for Claude Code and Codex |
| [GITHUB.md](GITHUB.md) | Queue-label and repository-enforcement setup |
| [QUEUE.md](QUEUE.md) | Reviewable queue snapshot; GitHub labels remain live state |
| [STATE.md](STATE.md) | Compact human-readable health snapshot |
| [DECISIONS.md](DECISIONS.md) | Accepted constraint changes and their evidence |
| [`runs/`](runs/README.md) | One immutable record per execution |

## Daily operating rule

Read the control room before starting more work. When the number of items awaiting review
reaches the charter limit, stop producing. The factory's useful throughput is bounded by
what a human can verify and understand, even when generation itself is cheap.
