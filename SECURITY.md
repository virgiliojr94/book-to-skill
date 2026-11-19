# Security Policy

## Scope

`book-to-skill` has a **zero-network Python core** (`book_to_skill/`): it does
**not** perform outbound HTTP requests, open sockets, upload your files, phone
home, or run a network service.

- **Mode 1 (Local files):** reads local document files you point it at and writes
  skill files to your skills directory.
- **Mode 2 (Search & Read via MCP):** your **host coding agent** mediates MCP calls
  (`search`, `get_details`, `read`) to an MCP server you configure;
  `book_to_skill/remote/` contains only deterministic, stdlib-only offline helpers
  that process JSON/text payloads passed by the agent.

The main security surface is:

- the Python extraction code (parsing untrusted local document files),
- untrusted text chunks and metadata returned by external MCP servers in Mode 2, and
- the optional local extractor dependencies it can install on request (`pip install …`
  when you choose `--install-missing yes`).

## Mode 2 (Search & Read via MCP) security boundaries

Mode 2 (`/book-to-skill search ...`) enforces the following boundaries:

- **Zero-network core & host-mediated MCP:** `book_to_skill/` never imports
  network clients, never opens sockets, and never depends on `libgen-mcp` or an
  MCP runtime. All MCP tool invocations (`search`, `get_details`, `read`) are
  performed by the host agent; MCP `download` is never used.
- **Sanitization of all remote fragments:** Every text chunk returned by MCP
  `read` is treated as untrusted external data and passed through
  `book_to_skill.sanitize.sanitize_extracted_text()` (via `sanitize_remote_chunk()`
  and `process_section_page()`) to strip invisible zero-width and Unicode
  tag-block characters before synthesis or inspection. Generated skills are also
  checked by `tools/scan_generated_skill.py`.
- **No permanent full-text storage:** Chapters are synthesized incrementally and
  raw fragments are discarded immediately after each `chapters/*.md` file is
  written. Mode 2 never writes `full_text.txt`, and both `remote_session.json`
  and provenance metadata forbid raw prose keys (`FORBIDDEN_PROSE_KEYS`), stored
  under a symlink-checked `0o700` `workdir` with `0o600` atomic writes.
- **Bounded pagination:** `book_to_skill/remote/reader.py` enforces per-section
  and total request caps (`max_cursors_per_section=100`, `max_total_requests=1000`)
  and stops immediately on repeated-cursor loops.
- **Explicit confirmation & `--private` publish default:** Policy is configured
  via `BOOK_TO_SKILL_REMOTE_POLICY` (defaults: `require_explicit_confirmation: true`,
  `default_publish_visibility: "private"`, `allow_public_publish: false`,
  `warn_mcp_temporary_cache: true`). Before any MCP `read` call, the agent must
  display work identity, known access/license metadata, and the notice that
  **user confirmation does not equal copyright-holder authorization**, and receive
  explicit user confirmation (never inferred). GitHub publishing defaults to
  `--private` and blocks public publishing unless both policy and explicit closed
  confirmation allow it.
- **Technical caveat — MCP server temporary cache & model transmission:** While
  `book_to_skill` itself makes no network calls and stores no permanent
  `full_text.txt`, invoking MCP `read` on an external MCP server (for example,
  `libgen-mcp`) may cause that MCP server to **temporarily download or cache full
  book files on the MCP server**, and read text chunks are **transmitted to your
  host agent's model context** for synthesis under the MCP provider's and model
  provider's own retention and data policies.

## Supported versions

The latest released `1.x` version receives fixes. Please reproduce issues against
the most recent tag before reporting.

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Instead use GitHub's
private vulnerability reporting:

- Go to the repository's **Security** tab → **Report a vulnerability**.

Include: affected version, a minimal reproduction (ideally a small sample file or
crafted input), and the impact you observed. We aim to acknowledge within a few days.

## Good practices for users

- Run `python3 scripts/extract.py --check` to see exactly which extractors are in
  use; install dependencies yourself if you prefer to control what is added.
- Only convert documents you trust and have the right to process (see the README's
  Copyright & fair-use section).
- In Mode 2, review your configured MCP server and `BOOK_TO_SKILL_REMOTE_POLICY`
  (`enabled_providers`, `blocked_providers`, `allow_public_publish`) before
  confirming a `read` request, and keep skills derived from third-party works
  private.
