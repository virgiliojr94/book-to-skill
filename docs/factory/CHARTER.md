# Factory charter

This is the human-owned policy for the single MiP pilot. Factory workflow rules operate
under MiP enterprise governance and this charter. Silence is not permission.

CHARTER_STATUS: ready

## 1. Tier

TIER: oss

This is a published open-source document-processing tool with downstream agent users.
Human review owns every merge, and autonomy is limited by the protected paths and review
back-pressure below.

## 2. Load-bearing paths

Changes to these paths require deep gates and a human read, except for a new test file
allowed by the test-file rule below. They are never auto-merged:

LOAD_BEARING:
  - "book_to_skill/**"
  - "scripts/**"
  - "tools/**"
  - "tests/**"
  - "SKILL.md"
  - "pyproject.toml"
  - "mkdocs.yml"
  - ".github/**"
  - ".factory/**"
  - ".claude/**"
  - ".agents/**"
  - ".codex/**"
  - "AGENTS.md"
  - "CLAUDE.md"
  - "SECURITY.md"
  - "CONTRIBUTING.md"

## 3. Protected paths

Protected paths are the Factory policy, agent permissions, CI, project contract, security
guidance, and all executable or tested extraction code:

PROTECTED_PATHS:
  - ".github/workflows/**"
  - ".factory/**"
  - ".claude/**"
  - ".agents/**"
  - ".codex/**"
  - "AGENTS.md"
  - "CLAUDE.md"
  - "book_to_skill/**"
  - "scripts/**"
  - "tools/**"
  - "tests/**"
  - "SKILL.md"
  - "pyproject.toml"
  - "mkdocs.yml"
  - "SECURITY.md"
  - "CONTRIBUTING.md"

## 4. Test-file rule

TESTS_ARE_LOAD_BEARING: true

An unattended run may add a new test file but may not modify an existing test file. An
interactive change to an existing test requires explicit human approval and a human read.

## 5. Automatable work

AUTOMATABLE:
  - Bounded bug fixes outside load-bearing paths with a reproducible failure
  - New tests for previously untested behavior without changing existing tests
  - Lint, format, and deterministic maintenance corrections
  - Documentation tied directly to code behavior outside protected policy paths
  - Small isolated refactors with behavioral equivalence outside load-bearing paths
  - Deterministic maintenance work that passes the full gates

NEEDS_HUMAN_REVIEW:
  - Architecture changes
  - Authentication or authorization
  - Financial calculations
  - Customer data
  - Databases or schema migrations
  - Secrets
  - Billing
  - Production infrastructure
  - Security controls
  - Dependency changes with meaningful system impact
  - Agent permissions
  - MiP governance
  - Deployments
  - Destructive operations
  - Any change to a load-bearing or protected path, except a new test file allowed by the
    test-file rule above

NEVER_AUTOMATE:
  - Merge decisions
  - Changes to this charter, contract, gate configuration, hooks, or permissions
  - Product intent or architectural direction
  - Any work not explicitly covered by AUTOMATABLE

## 6. Definition of done

DEFINITION_OF_DONE:
  - The required Factory gate level ends with FACTORY_GATES status=GREEN
  - The change has a test that fails without the implementation when behavior changes
  - No existing test file was changed by an unattended run
  - The diff does only the one thing described by the queue item
  - A fresh verifier reads the diff and independently accepts it
  - A human can understand the risk and evidence from the pull request
  - No merge, deployment, schedule, or issue-trigger write was performed; report-only
    acceptance writes no labels, and live triage label writes follow CONTRACT.md after a
    human authorizes triage

## 7. Gate policy

The project has no type-checker in its source tree or CI; the `types` gate is intentionally
not claimed. Lint, unit/integration tests, documentation build, security audit, and skill
contract validation use commands already defined by the repository's CI.

GATES:
  default: full
  load_bearing: deep
  docs_only: fast

Configured commands:

  - `lint`: Ruff E9/F check over the project code, scripts, tests, and tools
  - `test`: pytest suite plus the CI smoke extraction using a temporary sample
  - `build`: `mkdocs build`
  - `audit`: Bandit high-severity/high-confidence gate over executable Python
  - `architecture`: `python3 tools/validate_skill.py SKILL.md`, the repository's
    contract validation for the always-loaded skill

## 8. Stop conditions and review limit

STOP_IF:
  - A required gate is missing, skipped, misconfigured, or red
  - Gates are red twice in a row on the same item
  - The work touches a load-bearing or protected path without human approval
  - A non-bootstrap diff exceeds 400 changed lines
  - The item remains ambiguous after one clarification attempt
  - More than 3 items are awaiting human review
  - An independent verifier is unavailable
  - A command would merge, deploy, create a schedule, enable the issue trigger, or perform
    a destructive operation

REVIEW_LIMIT: 3

The initial Factory installation is a one-time bootstrap exception to the 400-line routine
diff limit. All later Factory or project changes remain subject to that limit.

No tier permits automatic merging. GitHub branch protection is the enforcement boundary;
Factory hooks are defense in depth.

## 9. Constraint review

Record any future loosening or tightening in `docs/factory/DECISIONS.md` with concrete
evidence. Review the pilot constraints after the first three completed review cycles or
after any escaped defect, whichever comes first.

LAST_REVIEWED: 2026-08-26
NEXT_REVIEW: 2026-09-26
