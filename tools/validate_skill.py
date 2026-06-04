#!/usr/bin/env python3
"""Audit a SKILL.md against Claude Code Agent Skills rules (Claude-only lens).

Severity:
  ERROR  -> breaks/degrades the skill ON CLAUDE CODE (fails CI)
  WARN   -> Claude ignores it, or it's a soft guideline (does not fail CI)

The repo is positioned as a Claude Code skill, so this checks Claude rules
only. Frontmatter keys aimed at other agents (e.g. Amp's `shell_command`,
`compatibility`, `argument-hint`) are reported as WARN because Claude Code
silently ignores them — they are intentional cross-agent metadata, not errors.

Refs:
  https://code.claude.com/docs/en/skills
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

Usage: python3 tools/validate_skill.py [path/to/SKILL.md]
"""
import re
import sys
from pathlib import Path

# Claude Code built-in tools. Bash grants may be scoped, e.g. "Bash(python3 *)".
CLAUDE_CODE_TOOLS = {
    "Bash", "Read", "Write", "Edit", "Glob", "Grep",
    "WebFetch", "WebSearch", "NotebookEdit", "Task", "TodoWrite",
}
RECOGNIZED_KEYS = {"name", "description", "allowed-tools", "license"}
RESERVED_NAME_WORDS = {"anthropic", "claude"}


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None, None
    end = text.find("\n---", 3)
    if end == -1:
        return None, None
    return text[3:end].lstrip("\n"), text[end + 4:]


def get_scalar(fm, key):
    m = re.search(rf"^{re.escape(key)}:\s*(.*)$", fm, re.MULTILINE)
    return m.group(1).strip().strip('"').strip("'") if m else None


def get_list_items(fm, key):
    items, capturing = [], False
    for ln in fm.splitlines():
        if re.match(rf"^{re.escape(key)}:\s*$", ln):
            capturing = True
            continue
        if capturing:
            m = re.match(r"^\s*-\s*(.+)$", ln)
            if m:
                items.append(m.group(1).strip())
            elif re.match(r"^[A-Za-z][\w-]*:", ln):
                break
    return items


def top_level_keys(fm):
    return [m.group(1) for ln in fm.splitlines()
            if (m := re.match(r"^([A-Za-z][\w-]*):", ln))]


def tool_base(entry):
    """Bash(python3 *) -> Bash ; Read -> Read."""
    return entry.split("(", 1)[0].strip()


def audit(path):
    text = Path(path).read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    errors, warns = [], []
    if fm is None:
        return ["no valid YAML frontmatter (--- block)"], []

    name = get_scalar(fm, "name")
    if not name:
        errors.append("name: missing (required)")
    else:
        if len(name) > 64:
            errors.append(f"name: {len(name)} > 64 chars")
        if not re.fullmatch(r"[a-z0-9-]+", name):
            errors.append(f"name: '{name}' must be lowercase letters/digits/hyphens")
        if any(w in name.lower() for w in RESERVED_NAME_WORDS):
            errors.append(f"name: '{name}' contains a reserved word")

    desc = get_scalar(fm, "description")
    if not desc:
        errors.append("description: missing (required)")
    elif len(desc) > 1024:
        errors.append(f"description: {len(desc)} > 1024 chars")

    # Tool grant analysis (Claude lens)
    tools = get_list_items(fm, "allowed-tools")
    if not tools:
        inline = get_scalar(fm, "allowed-tools")
        if inline:
            tools = inline.split()
    if tools:  # a restriction is declared -> Claude Code enforces it
        bases = {tool_base(t) for t in tools}
        claude_valid = bases & CLAUDE_CODE_TOOLS
        unknown = [t for t in tools if tool_base(t) not in CLAUDE_CODE_TOOLS]
        uses_bash = bool(re.search(r"```bash", body)) or "python3 " in body
        if uses_bash and "Bash" not in bases:
            errors.append("allowed-tools declares a restriction but omits 'Bash', yet the "
                          "skill runs bash/python3 — under Claude Code those steps would be blocked")
        if not claude_valid:
            errors.append("allowed-tools: no recognized Claude Code tool in the list")
        if unknown:
            warns.append(f"allowed-tools: {unknown} are not Claude Code tool names "
                         "(ignored by Claude)")

    for k in top_level_keys(fm):
        if k not in RECOGNIZED_KEYS:
            warns.append(f"frontmatter '{k}': not a recognized Claude Code key (ignored by Claude)")

    n = len(text.splitlines())
    if n > 500:
        warns.append(f"body: {n} lines > 500 (soft guideline for optimal performance)")

    return errors, warns


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "SKILL.md"
    errors, warns = audit(target)
    for w in warns:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    if errors:
        print(f"✗ {target}: {len(errors)} error(s), {len(warns)} warning(s)")
        sys.exit(1)
    print(f"✓ {target}: no Claude-breaking issues ({len(warns)} warning(s))")


if __name__ == "__main__":
    main()
