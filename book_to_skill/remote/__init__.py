"""Offline helpers for MCP-assisted discovery, policy, reading, and provenance."""

from __future__ import annotations

from book_to_skill.remote.checkpoint import (
    DEFAULT_LIMITS,
    SCHEMA_VERSION,
    SESSION_FILENAME,
    VALID_CHAPTER_STATUSES,
    VALID_OUTLINE_MODES,
    init_remote_session,
    load_remote_session,
    pending_chapters,
    save_remote_session,
    update_chapter_progress,
)
from book_to_skill.remote.coverage import (
    COVERAGE_REPORT_KEYS,
    build_coverage_report,
    format_coverage_summary,
)
from book_to_skill.remote.discovery import (
    compute_dedup_key,
    format_candidate_selection_table,
    group_duplicate_editions,
    normalize_search_results,
    normalize_work_details,
)
from book_to_skill.remote.policy import (
    DEFAULT_POLICY,
    POLICY_ENV_VAR,
    build_access_copyright_notice,
    check_provider_allowed,
    load_policy,
    resolve_publish_visibility,
    verify_user_confirmation,
)
from book_to_skill.remote.provenance import (
    FORBIDDEN_PROSE_KEYS,
    STORAGE_MODE,
    build_remote_provenance,
    render_provenance_markdown,
)
from book_to_skill.remote.reader import (
    SUPPORTED_READ_MODES,
    parse_outline_response,
    process_section_page,
    read_section_from_pages,
    sanitize_remote_chunk,
)

__all__ = [
    "COVERAGE_REPORT_KEYS",
    "DEFAULT_LIMITS",
    "DEFAULT_POLICY",
    "FORBIDDEN_PROSE_KEYS",
    "POLICY_ENV_VAR",
    "SCHEMA_VERSION",
    "SESSION_FILENAME",
    "STORAGE_MODE",
    "SUPPORTED_READ_MODES",
    "VALID_CHAPTER_STATUSES",
    "VALID_OUTLINE_MODES",
    "build_access_copyright_notice",
    "build_coverage_report",
    "build_remote_provenance",
    "check_provider_allowed",
    "compute_dedup_key",
    "format_candidate_selection_table",
    "format_coverage_summary",
    "group_duplicate_editions",
    "init_remote_session",
    "load_policy",
    "load_remote_session",
    "normalize_search_results",
    "normalize_work_details",
    "parse_outline_response",
    "pending_chapters",
    "process_section_page",
    "read_section_from_pages",
    "render_provenance_markdown",
    "resolve_publish_visibility",
    "sanitize_remote_chunk",
    "save_remote_session",
    "update_chapter_progress",
    "verify_user_confirmation",
]
