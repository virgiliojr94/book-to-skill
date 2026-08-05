#!/usr/bin/env python3
"""Advisory scan for prompt injection and unsafe authority in generated skills."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


MAX_SKILL_FILES = 1_000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
SUPPORTING_FILENAMES = ("glossary.md", "patterns.md", "cheatsheet.md")

# Reuse the extractor's invisible-code-point set instead of duplicating it, so
# the two injection defenses cannot drift apart. They previously did: the
# extractor did not strip U+2060 while this scanner flagged it, so a generated
# skill was warned about a character extraction was meant to have removed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from book_to_skill.sanitize import is_invisible_codepoint  # noqa: E402

_CONTENT_RULES = (
    (
        "prompt.ignore_previous",
        re.compile(
            r"\bignore\s+(?:(?:all|any|the)\s+)?(?:previous|prior)\s+"
            r"(?:instructions?|prompts?|rules?|messages?)\b",
            re.IGNORECASE,
        ),
        "contains an instruction-override phrase",
    ),
    (
        "prompt.disregard_system",
        re.compile(r"\bdisregard\s+(?:the\s+)?(?:system|developer)\b", re.IGNORECASE),
        "contains a system-instruction override phrase",
    ),
    (
        "prompt.role_reassignment",
        re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
        "contains a role-reassignment phrase",
    ),
    (
        "prompt.fake_system_prefix",
        re.compile(r"^\s*(?:[-*]\s*)?(?:system|developer)\s*:", re.IGNORECASE),
        "contains a system-like message prefix",
    ),
    (
        "prompt.system_tag",
        re.compile(r"<\s*/?\s*system\b[^>]*>", re.IGNORECASE),
        "contains a system-message tag",
    ),
    (
        "prompt.chat_template_tag",
        re.compile(r"<\|\s*im_start\s*\|>|\[\s*INST\s*\]", re.IGNORECASE),
        "contains a model chat-template delimiter",
    ),
    (
        "prompt.tool_call_tag",
        re.compile(r"\btool[_ -]?call\b", re.IGNORECASE),
        "contains a tool-call control token",
    ),
)

_EXFILTRATION_TERM = re.compile(r"\bexfiltrat(?:e|es|ed|ing|ion)\b", re.IGNORECASE)
_OUTBOUND_TERM = re.compile(
    r"\b(?:curl|wget|send|post|upload|transmit)\b|https?://",
    re.IGNORECASE,
)
_SENSITIVE_TERM = re.compile(
    r"(?:\.env\b|\bbase64\b|\bsecrets?\b|\bcredentials?\b|\bapi[_ -]?keys?\b)",
    re.IGNORECASE,
)


class ScanError(RuntimeError):
    """Raised when the scanner cannot inspect the complete generated skill."""


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule_id: str
    message: str


def _is_invisible(codepoint: int) -> bool:
    return is_invisible_codepoint(codepoint)


def _terminal_safe(value: str) -> str:
    """Escape control and non-ASCII characters before printing untrusted paths."""
    return value.encode("unicode_escape", errors="backslashreplace").decode("ascii")


def _frontmatter_line_numbers(lines: Sequence[str]) -> set[int]:
    if not lines or lines[0].strip() != "---":
        return set()
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return set(range(2, index))
    return set()


def _walk_markdown(directory: Path) -> list[Path]:
    """Collect ``*.md`` under ``directory`` at any depth, ignoring symlinks.

    ``os.walk(followlinks=False)`` rather than ``Path.rglob``: before Python 3.13
    ``rglob`` descends into symlinked directories, which would let a generated
    skill walk the scanner outside its own tree. Symlinked *files* are left in
    the list and rejected later by :func:`_read_skill_files`, so a planted
    symlink is reported as an error rather than silently skipped.
    """
    found: list[Path] = []
    for walk_root, _dirnames, filenames in os.walk(directory, followlinks=False):
        for filename in filenames:
            if filename.lower().endswith(".md"):
                found.append(Path(walk_root) / filename)
    return found


def unscanned_markdown(path: Path) -> list[str]:
    """Markdown files present in the skill directory but outside the scan scope.

    The scope is deliberately bounded to what book-to-skill generates (SKILL.md,
    the supporting files, and ``chapters/``), so unrelated notes in the directory
    are not scanned and cannot raise false findings. The risk is the *reporting*:
    printing "scan passed" while files the agent will happily read went unopened
    is a false assurance. Listing them keeps the bounded scope honest.
    """
    requested = path.expanduser()
    root = (requested.parent if requested.name.lower() == "skill.md" else requested)
    root = root.resolve(strict=True)
    scanned = set(_collect_skill_files(requested))
    return sorted(
        candidate.relative_to(root).as_posix()
        for candidate in _walk_markdown(root)
        if candidate not in scanned
    )


def _collect_skill_files(skill_dir: Path) -> list[Path]:
    requested = skill_dir.expanduser()
    if requested.name.lower() == "skill.md" and requested.is_file():
        requested = requested.parent
    if requested.is_symlink():
        raise ScanError("the generated skill directory must not be a symbolic link")
    try:
        root = requested.resolve(strict=True)
    except OSError as exc:
        raise ScanError("the generated skill directory does not exist") from exc
    if not root.is_dir():
        raise ScanError("the generated skill path is not a directory")

    master = root / "SKILL.md"
    if not master.is_file() or master.is_symlink():
        raise ScanError("SKILL.md is missing or is a symbolic link")

    candidates = {master}
    for filename in SUPPORTING_FILENAMES:
        supporting_file = root / filename
        if supporting_file.is_symlink():
            raise ScanError(f"{filename} must be a real file, not a symbolic link")
        if supporting_file.exists():
            if not supporting_file.is_file():
                raise ScanError(f"{filename} must be a real file")
            candidates.add(supporting_file)

    chapters = root / "chapters"
    if chapters.exists():
        if chapters.is_symlink() or not chapters.is_dir():
            raise ScanError("chapters must be a real directory, not a symbolic link")
        candidates.update(_walk_markdown(chapters))

    files = sorted(candidates, key=lambda path: path.relative_to(root).as_posix().lower())
    if len(files) > MAX_SKILL_FILES:
        raise ScanError(
            f"generated skill has {len(files):,} Markdown files; maximum is "
            f"{MAX_SKILL_FILES:,}"
        )
    return files


def _read_skill_files(skill_dir: Path, files: Iterable[Path]) -> Iterable[tuple[str, str]]:
    total_bytes = 0
    for path in files:
        if path.is_symlink():
            raise ScanError("generated skill contains a symbolic-link Markdown file")
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ScanError(
                f"{_terminal_safe(path.name)} is {size:,} bytes; maximum scanned file size is "
                f"{MAX_FILE_BYTES:,} bytes"
            )
        total_bytes += size
        if total_bytes > MAX_TOTAL_BYTES:
            raise ScanError(
                f"generated skill Markdown exceeds the {MAX_TOTAL_BYTES:,}-byte scan limit"
            )
        relative = path.relative_to(skill_dir).as_posix()
        try:
            yield relative, path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ScanError(f"{_terminal_safe(relative)} is not valid UTF-8") from exc
        except OSError as exc:
            raise ScanError(f"could not read {_terminal_safe(relative)}") from exc


def _scan_text(relative_path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    frontmatter_lines = _frontmatter_line_numbers(lines)

    for line_number, line in enumerate(lines, start=1):
        invisible = sorted({ord(char) for char in line if _is_invisible(ord(char))})
        if invisible:
            codepoints = ", ".join(f"U+{value:04X}" for value in invisible)
            findings.append(
                Finding(
                    relative_path,
                    line_number,
                    "unicode.invisible",
                    f"contains invisible Unicode code point(s): {codepoints}",
                )
            )

        for rule_id, pattern, message in _CONTENT_RULES:
            if pattern.search(line):
                findings.append(Finding(relative_path, line_number, rule_id, message))

        if _EXFILTRATION_TERM.search(line) or (
            _OUTBOUND_TERM.search(line) and _SENSITIVE_TERM.search(line)
        ):
            findings.append(
                Finding(
                    relative_path,
                    line_number,
                    "tool.exfiltration_shape",
                    "contains exfiltration-shaped tool or sensitive-data language",
                )
            )

        if line_number in frontmatter_lines:
            if re.match(r"^\s*allowed-tools\s*:", line, re.IGNORECASE):
                findings.append(
                    Finding(
                        relative_path,
                        line_number,
                        "frontmatter.allowed_tools",
                        "generated frontmatter declares or widens tool authority",
                    )
                )
            if re.match(
                r"^\s*disable-model-invocation\s*:\s*"
                r"[\"']?(?:false|no|0)[\"']?\s*(?:#.*)?$",
                line,
                re.IGNORECASE,
            ):
                findings.append(
                    Finding(
                        relative_path,
                        line_number,
                        "frontmatter.model_invocation_enabled",
                        "generated frontmatter explicitly enables model invocation",
                    )
                )

    return findings


def scan_generated_skill(path: Path) -> list[Finding]:
    requested = path.expanduser()
    skill_dir = requested.parent if requested.name.lower() == "skill.md" else requested
    files = _collect_skill_files(requested)
    root = skill_dir.resolve(strict=True)
    findings: list[Finding] = []
    for relative_path, text in _read_skill_files(root, files):
        findings.extend(_scan_text(relative_path, text))
    return sorted(findings, key=lambda item: (item.path.lower(), item.line, item.rule_id))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Generated skill directory or its SKILL.md")
    args = parser.parse_args(argv)

    try:
        findings = scan_generated_skill(Path(args.path))
        skipped = unscanned_markdown(Path(args.path))
    except ScanError as exc:
        print(f"ERROR generated-skill scan incomplete: {exc}", file=sys.stderr)
        return 2

    if skipped:
        # Advisory only, and deliberately not a Finding: the bounded scope is
        # intentional, so these files must not change the exit code. But the
        # user has to know the "passed" line below does not cover them.
        print(
            f"Note: {len(skipped)} Markdown file(s) in the skill directory are "
            "outside the generated-skill scope and were NOT scanned:"
        )
        for relative in skipped:
            print(f"  SKIP {_terminal_safe(relative)}")
        print(
            "  Scope is SKILL.md, glossary/patterns/cheatsheet, and chapters/. "
            "Move generated content there to have it scanned."
        )

    if findings:
        print(f"Generated-skill scan found {len(findings)} advisory finding(s):")
        for finding in findings:
            print(
                f"  WARN {_terminal_safe(finding.path)}:{finding.line} "
                f"[{finding.rule_id}] {finding.message}"
            )
        print("Review the generated files before loading, installing, or publishing them.")
        print(
            "Rules are intentionally broad and may match legitimate AI/LLM or "
            "systems-topic text; review each finding in context."
        )
        print("No files were modified by this scan.")
        return 1

    scope = " in the scanned scope" if skipped else ""
    print(
        f"Generated-skill scan passed: no known injection or authority patterns "
        f"found{scope}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
