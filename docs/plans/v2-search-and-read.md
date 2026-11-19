# Release v2.0 Plan: Search & Read (MCP-Assisted Discovery & Incremental Remote Generation)

Status: **ACTIVE EXECUTION PLAN — PR 0–5**

This document is the **shared execution state and contract ledger** for `book-to-skill` v2.0 (`Search & Read`).
Every coding or verification agent MUST read this document first, locate its assigned task or the next `READY` task whose dependencies are `DONE`, respect file ownership boundaries, obey the frozen interface contracts below, run all validation gates, and record actual command output in the **Evidence Ledger** before marking any task `DONE`.

---

## 1. Architectural Invariants (Non-Negotiable)

1. **Two input modes, one skill output contract:**
   - **Mode 1 — Local (unchanged):** File/dir/glob → Python extractor (`book_to_skill/`) → `full_text.txt` + `metadata.json` → Generator (`SKILL.md`). Must continue working with zero MCP tools and zero optional dependencies (`CI/smoke` green).
   - **Mode 2 — Search & Read (new):** Query (`/book-to-skill search ...`) → Host Agent calls MCP (`search`, `get_details`, `read`) → Python offline helpers (`book_to_skill/remote/`) normalize, check policy, sanitize, track cursors/checkpoints, compute coverage/provenance → Incremental chapter generation → Same skill output (`SKILL.md`, `chapters/`, `glossary.md`, `patterns.md`, `cheatsheet.md`).
2. **Strict Zero-Network Boundary in Python Core (`SECURITY.md`):**
   - `book_to_skill/` MUST NOT perform outbound HTTP requests, open sockets, embed Go code from `libgen-mcp`, or require `libgen-mcp` as a runtime dependency.
   - The **host coding agent** invokes MCP tools (`search`, `get_details`, `read`); `book_to_skill/remote/` consists purely of **deterministic stdlib-only offline helpers** operating on JSON/text payloads passed by the agent/CLI/tests.
3. **Keep `SKILL.md` Lean (Progressive Disclosure):**
   - Root `SKILL.md` (currently 880 lines) gets only a compact Mode 2 router/trigger and pointer.
   - Full Mode 2 instructions live in `references/search-and-read.md`, loaded lazily only when Mode 2 is invoked.
   - Do not break `tests/test_publish_visibility_gate.py` (Step 11 `--private` gate wording must remain intact).
4. **Untrusted External Data & No Permanent Raw Book Storage:**
   - All remote MCP text MUST pass through `book_to_skill.sanitize.sanitize_extracted_text()` before synthesis or inspection.
   - Mode 2 MUST NOT save a permanent `full_text.txt` or download the full book file via `download`. Raw chapter fragments are discarded after synthesis.
   - `remote_session.json` and `provenance` metadata MUST NEVER persist raw copyrighted prose.
5. **Python 3.9+ Compatibility & Conventional Commits:**
   - Target `requires-python = ">=3.9"` (`from __future__ import annotations`).
   - Do not edit `CHANGELOG.md` manually; PR titles/commits must follow Conventional Commits.

---

## 2. Frozen Interface Contracts (Zero-Drift Schema)

Agents implementing PR 2, PR 3, PR 4, and PR 5 MUST build to these exact schemas:

### Contract A — `NormalizedWorkCandidate` (`book_to_skill/remote/discovery.py`)
Produced by normalizing MCP `search` / `get_details` payloads:
```json
{
  "provider": "libgen-mcp",
  "item_id": "string",
  "title": "string",
  "authors": ["string"],
  "edition": "string | null",
  "year": "int | null",
  "format": "string | null",
  "language": "string | null",
  "identifiers": {
    "isbn": ["string"],
    "doi": "string | null"
  },
  "source_name": "string",
  "access_info": "string",
  "license_info": "string | null",
  "dedup_key": "string"
}
```
- `normalize_search_results(raw_results: list[dict], provider: str = "libgen-mcp") -> list[dict]`
- `normalize_work_details(raw_details: dict, provider: str = "libgen-mcp") -> dict`
- `group_duplicate_editions(candidates: list[dict]) -> list[dict]` (groups candidates sharing `dedup_key` while keeping selectable editions explicit).

### Contract B — `RemotePolicyConfig` & Copyright Gate (`book_to_skill/remote/policy.py`)
Configurable without rewriting the pipeline (via env var `BOOK_TO_SKILL_REMOTE_POLICY` JSON/path or explicit dict):
```json
{
  "enabled_providers": ["*"],
  "blocked_providers": [],
  "require_explicit_confirmation": true,
  "default_publish_visibility": "private",
  "allow_public_publish": false,
  "warn_mcp_temporary_cache": true
}
```
- `load_policy(config_override: dict | None = None) -> dict`
- `check_provider_allowed(provider: str, policy: dict) -> tuple[bool, str]`
- `build_access_copyright_notice(candidate: dict, policy: dict) -> str`
  Must display: source/provider, work title/authors/edition/identifiers, known license/access info, explicit statement that **user confirmation does not equal copyright-holder authorization**, and technical note that MCP `read` may use temporary server cache / transmit text to the model.
- `verify_user_confirmation(reply: str, candidate: dict, policy: dict) -> bool` (explicit consent required; never inferred).

### Contract C — `RemoteReader` & `RemoteSessionState` (`book_to_skill/remote/reader.py`, `checkpoint.py`)
Reader step contract (host passes raw MCP `read` response dicts into Python offline processors):
- Supported `read` modes: `"outline"`, `"section"`, `"cursor"`.
- `sanitize_remote_chunk(raw_text: str) -> dict` returning `{"text": str, "removed_invisible_count": int, "empty": bool}`.
- `parse_outline_response(raw_outline: dict) -> tuple[str, list[dict]]` -> returns `(outline_mode, chapters)` where `outline_mode` is `"outline"` or `"sequential_fallback"`, and each chapter entry has `{"index": int, "section_id": str, "title": str}`.
- `process_section_page(raw_page: dict, *, seen_cursors: set[str], max_cursors_per_section: int = 100) -> dict`:
  - Runs `sanitize_extracted_text()`.
  - Detects `next_cursor`, `truncated` flags, missing/empty sections, and **infinite cursor loops** (if `next_cursor in seen_cursors` or limit reached -> stops with `status="incomplete"` and explicit reason).
- `remote_session.json` schema inside per-run `workdir` (chmod `0700`, atomic write via temp + `os.replace`, **ZERO raw prose stored**):
```json
{
  "schema_version": 1,
  "session_id": "string",
  "provider": "string",
  "work": { "item_id": "...", "title": "...", "authors": [], "edition": null, "identifiers": {} },
  "confirmed_by_user": true,
  "outline_mode": "outline",
  "limits": { "max_cursors_per_section": 100, "max_total_requests": 1000 },
  "chapters": [
    {
      "index": 1,
      "section_id": "ch1",
      "title": "string",
      "status": "pending | in_progress | done | incomplete | failed",
      "next_cursor": "string | null",
      "chunks_read": 0,
      "sanitized_removed_count": 0,
      "truncated": false,
      "error_reason": "string | null"
    }
  ]
}
```
- Resume contract: `pending_chapters(session)` skips `done` chapters without re-reading them; preserves/resumes from saved `next_cursor` or flags `incomplete`/`failed`.

### Contract D — `CoverageReport` & `RemoteProvenance` (`book_to_skill/remote/coverage.py`, `provenance.py`)
- `build_coverage_report(session: dict) -> dict`:
  Returns `{"chapters_total": int, "chapters_done": int, "chapters_incomplete": int, "chapters_failed": int, "missing_sections": list, "truncated_sections": list, "completeness_status": "complete" | "partial" | "degraded", "warnings": list[str]}`.
- `build_remote_provenance(candidate: dict, session: dict, policy: dict) -> dict`:
  Returns traceable edition/source/identifier/provider metadata + coverage summary, guaranteed free of raw book prose.

---

## 3. Task Ledger

Status values:
- `READY` — dependencies complete; an agent may claim it.
- `BLOCKED` — waiting on dependencies.
- `IN_PROGRESS` — claimed by an agent (Branch/Worker recorded).
- `DONE` — implemented + all acceptance gates verified with output below.

| ID | PR | Status | Owner | Depends on | Scope / Owned Files | Links to Success Criteria |
|---|---|---|---|---|---|---|
| **SR-00** | PR 0 | DONE | `coordinator` | — | `docs/plans/v2-search-and-read.md`, `AGENTS.md` | Shared state foundation |
| **SR-01** | PR 1 | DONE | `spec-dev` | SR-00 | `SKILL.md` | #1 |
| **SR-02** | PR 1 | DONE | `spec-dev` | SR-00 | `references/search-and-read.md` | #1, #2 |
| **SR-03** | PR 1 | DONE | `spec-dev` + `verifier` | SR-01, SR-02 | `tests/test_search_and_read_spec.py` | #1 |
| **SR-04** | PR 2 | DONE | `discovery-dev` + `verifier` | SR-00 | `book_to_skill/remote/__init__.py`, `book_to_skill/remote/discovery.py` | #2, #6 |
| **SR-05** | PR 2 | DONE | `policy-dev` + `verifier` | SR-00 | `book_to_skill/remote/policy.py` | #6, #8 |
| **SR-06** | PR 2 | DONE | `discovery-dev`/`policy-dev` + `verifier` | SR-04, SR-05 | `tests/remote/test_discovery.py`, `tests/remote/test_policy.py` | #2, #7, #8 |
| **SR-07** | PR 3 | DONE | `reader-dev` + `verifier` | SR-00, SR-04 | `book_to_skill/remote/reader.py` | #2, #4, #5 |
| **SR-08** | PR 3 | DONE | `reader-dev` + `verifier` | SR-07 | `book_to_skill/remote/checkpoint.py` | #4, #5, #6 |
| **SR-09** | PR 3 | DONE | `reader-dev` + `verifier` | SR-07, SR-08 | `tests/remote/test_reader.py`, `tests/remote/test_checkpoint.py` | #5, #7 |
| **SR-10** | PR 4 | DONE | `gen-dev` + `verifier` | SR-05 + Contract C | `book_to_skill/remote/provenance.py`, `book_to_skill/remote/coverage.py`, `tests/remote/test_provenance_coverage.py` | #3, #4, #5, #6 |
| **SR-11** | PR 4 | DONE | `spec-dev` + `verifier` | SR-02, SR-10, SR-08 | `references/search-and-read.md`, `SKILL.md` (minimal hook), `book_to_skill/remote/__init__.py` | #3, #4, #8 |
| **SR-12** | PR 4 | DONE | `spec-dev` + `verifier` | SR-10, SR-11 | `tests/remote/test_incremental_generation.py` | #3, #4, #7 |
| **TR-LEG** | Track | READY | `User / Legal` | — | Legal review & `RemotePolicyConfig` defaults | #8 |
| **SR-13** | PR 5 | DONE | `qa-sec` + `verifier` | SR-06, SR-09, SR-10 | `tests/remote/mock_mcp.py`, `tests/remote/test_e2e_mock_mcp.py` | #1–#7 |
| **SR-14** | PR 5 | DONE | `qa-sec` + `verifier` | SR-13 | `tests/remote/test_security_boundaries.py`, policy review | #4, #8 |
| **SR-15** | Rel 2.0 | READY | `docs-dev` + `coordinator` | SR-14, TR-LEG | Docs (`README.md`, `docs/architecture.md`, `SECURITY.md`) DONE; version bump (`pyproject.toml` → `2.0.0`) + `git-cliff` `CHANGELOG.md` + tag pending user/legal release cut | #1–#8 |

---

## 4. Validation Gates (Required Before Marking Any Task `DONE`)

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
python3 tools/validate_skill.py SKILL.md
```
Additional checks for remote/security PRs:
- `python3 tools/validate_skill.py --lens <all 6 lenses> SKILL.md`
- Verify 0 outbound network imports (`urllib`, `http.client`, `requests`, `httpx`, `socket`) in `book_to_skill/`.
- Verify generated skills in mocked E2E tests pass `tools/scan_generated_skill.py` and `tools/validate_skill.py`.

---

## 5. Evidence Ledger

### SR-00 — Shared execution plan and frozen interface contracts
- **Status:** `DONE`
- **Owner:** `coordinator`
- **Artifacts:** `docs/plans/v2-search-and-read.md`, `AGENTS.md`
- **Notes:** Baseline `master` at `e7bb659` (`968 passed, 12 skipped, 12 subtests passed`, `ruff check .` clean). Contracts A–D frozen for parallel agents.

### PR 1 (SR-01, SR-02, SR-03) — Input Modes & Lazy Search & Read Spec
- **Status:** `DONE` (integrated at `7582b5c` on `feat/v2-search-and-read`)
- **Owner:** `spec-dev`, verified by `verifier`
- **Artifacts:** `SKILL.md` (+9/-3, net +6 lines), `references/search-and-read.md` (+95), `tests/test_search_and_read_spec.py` (+115)
- **Gates:** All 6 `validate_skill.py` lenses exited 0; `pytest -q` & `ruff check .` green.

### PR 2 (SR-04, SR-05, SR-06) — Discovery Normalization & Policy/Copyright Gate
- **Status:** `DONE` (integrated at `ff12af7` and `98d1ff7` on `feat/v2-search-and-read`)
- **Owner:** `discovery-dev` + `policy-dev`, verified by `verifier`
- **Artifacts:** `book_to_skill/remote/__init__.py`, `book_to_skill/remote/discovery.py`, `book_to_skill/remote/policy.py`, `tests/remote/test_discovery.py`, `tests/remote/test_policy.py`
- **Integrated Gates:** `pytest -q` -> `1051 passed, 12 skipped, 12 subtests passed in 5.38s`; `ruff check .` -> `All checks passed!`; `bandit` HIGH gate -> 0 issues; `validate_skill.py` -> passed.

### PR 3 (SR-07, SR-08, SR-09) — Controlled Remote Reader & Resumable Checkpoints
- **Status:** `DONE` (integrated at `1a20ef5` on `feat/v2-search-and-read`)
- **Owner:** `reader-dev`, verified by `verifier`
- **Artifacts:** `book_to_skill/remote/reader.py`, `book_to_skill/remote/checkpoint.py`, `tests/remote/test_reader.py`, `tests/remote/test_checkpoint.py`
- **Gates:** 34 new unit tests passing; prompt-injection sanitization via `sanitize_extracted_text()`; cursor loop/limit guards; atomic `0o700` session writes with symlink check and zero raw prose stored.

### PR 4a (SR-10) — Coverage Reporting & Prose-Free Provenance Metadata
- **Status:** `DONE` (integrated at `a0885e6` on `feat/v2-search-and-read`)
- **Owner:** `gen-dev`, verified by `verifier`
- **Artifacts:** `book_to_skill/remote/coverage.py`, `book_to_skill/remote/provenance.py`, `tests/remote/test_provenance_coverage.py`
- **Integrated Gates:** `pytest -q` -> `1095 passed, 12 skipped, 12 subtests passed in 5.92s`; `ruff check .` -> `All checks passed!`; `bandit` HIGH gate -> 0 issues.

### PR 4b (SR-11, SR-12) — Incremental Generation Wiring & Contract Parity
- **Status:** `DONE` (integrated at `fa68e86` on `feat/v2-search-and-read`)
- **Owner:** `spec-dev`, verified by `verifier`
- **Artifacts:** `book_to_skill/remote/__init__.py` (re-exporting public API), `references/search-and-read.md`, `SKILL.md` (+2 lines, 888 total, Step 11 `--private` gate preserved), `tests/remote/test_incremental_generation.py`
- **Gates:** All 6 `validate_skill.py` lenses exited 0; `pytest -q` -> `1098 passed`; `ruff check .` clean; `bandit` 0 issues.

### PR 5 (SR-13, SR-14, SR-15 Docs) — Offline Mock MCP E2E, Security Boundaries & Docs
- **Status:** `DONE` (integrated at `fd65546` and `4a77b1a` on `feat/v2-search-and-read`); release version bump/tag awaits `TR-LEG` + maintainer release cut.
- **Owner:** `qa-sec` + `docs-dev`, verified by `verifier`
- **Artifacts:** `tests/remote/mock_mcp.py`, `tests/remote/test_e2e_mock_mcp.py`, `tests/remote/test_security_boundaries.py`, `docs/architecture.md`, `SECURITY.md`, `README.md`
- **Gates:** Static AST zero-network check across `book_to_skill/`; `MockMCPServer` coverage of timeout, cancel, corrupt cursor, cursor loop, truncated/missing chapters, inconsistent metadata, prompt injection; `pytest -q`, `ruff check .`, `validate_skill.py`, and `bandit` all green.
