# Factory run records

Write one immutable Markdown file per run. This avoids merge conflicts between parallel
routines and leaves enough structured evidence to measure the factory later.

Use a filename that is unique without coordination:

```
YYYY-MM-DDTHHMMSSZ-<stage>-<issue-or-run-id>.md
```

Start each file with this front matter:

```yaml
---
run_id: 2026-08-18T153012Z-implement-142
stage: triage | spec | implement | verify | monitor
started_at: 2026-08-18T15:30:12Z
finished_at: 2026-08-18T15:41:09Z
status: succeeded | stopped | rejected | infrastructure-failed
issue: 142 | none
pull_request: 318 | none
gate_level: fast | full | deep | none
gate_status: GREEN | RED | MISCONFIGURED | not-run
verifier: accepted | accepted-with-reservations | rejected | not-run
human_required: true | false
---
```

Then record what was checked, what changed, what was clean, and why the run stopped. Do not
include secrets, full transcripts, or copied issue bodies. Link to those systems instead.

These records support simple measurements without a separate service: queue age, gate
failure rate, verifier rejection rate, time to review, and escaped defects linked back to a
run or pull request.
