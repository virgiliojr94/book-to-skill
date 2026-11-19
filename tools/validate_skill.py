#!/usr/bin/env python3
"""Audit a SKILL.md against Agent Skills rules for a chosen host (lens).

Severity:
  ERROR  -> breaks/degrades the skill on the chosen host (fails CI)
  WARN   -> the host ignores it, or it's a soft guideline (does not fail CI)

Lenses:
  claude   — Claude Code rules (default; back-compat)
  copilot  — GitHub Copilot CLI rules
  amp      — Sourcegraph Amp rules
  hermes   — Hermes Agent rules
  openclaw — OpenClaw rules
  opencode — OpenCode rules

The SKILL.md format itself is an open standard
(https://github.com/agentskills/agentskills) — `name` + `description` are the
only universally-required fields. Lenses differ on which `allowed-tools` names
are recognized and which extra frontmatter keys are accepted vs. silently
ignored.

Refs:
  Claude     https://code.claude.com/docs/en/skills
             https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
  Copilot    https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
             https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills
  Amp        https://ampcode.com/manual#skills
  Hermes     https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
  OpenClaw   https://docs.openclaw.ai/tools/skills
  OpenCode   https://opencode.ai/docs/skills

Usage: python3 tools/validate_skill.py [--lens claude|copilot|amp|hermes|openclaw|opencode] [path/to/SKILL.md]
"""
import argparse
import re
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr so the ✓ / ✗ result glyphs don't raise
# UnicodeEncodeError on Windows consoles that default to a legacy code page
# (e.g. GBK / cp936).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Claude Code built-in tools. Bash grants may be scoped, e.g. "Bash(python3 *)".
CLAUDE_CODE_TOOLS = {
    "Bash", "Read", "Write", "Edit", "Glob", "Grep",
    "WebFetch", "WebSearch", "NotebookEdit", "Task", "TodoWrite",
}

# Copilot CLI recognized literal tool tokens. Anything else is assumed to be an
# MCP-server name (free-form), which Copilot accepts — so unknown tokens get a
# soft note, not an error.
COPILOT_CLI_TOOLS = {"shell", "bash", "write"}

# Amp accepts Claude's tool names plus its own `shell_command` shorthand.
AMP_TOOLS = CLAUDE_CODE_TOOLS | {"shell_command"}

LENSES = {
    "claude": {
        "label": "Claude Code",
        "tools": CLAUDE_CODE_TOOLS,
        "recognized_keys": {"name", "description", "allowed-tools", "license"},
        "reserved_name_words": {"anthropic", "claude"},
        "bash_tool_names": {"Bash"},
        "unknown_tool_severity": "error",
    },
    "copilot": {
        "label": "GitHub Copilot CLI",
        "tools": COPILOT_CLI_TOOLS,
        "recognized_keys": {"name", "description", "allowed-tools", "license"},
        "reserved_name_words": set(),
        "bash_tool_names": {"shell", "bash"},
        # Unknown tokens are likely MCP server names — Copilot accepts them.
        "unknown_tool_severity": "warn",
    },
    "amp": {
        "label": "Amp",
        "tools": AMP_TOOLS,
        "recognized_keys": {
            "name", "description", "allowed-tools", "license",
            "compatibility", "argument-hint",
        },
        "reserved_name_words": set(),
        "bash_tool_names": {"shell_command", "Bash"},
        "unknown_tool_severity": "warn",
    },
    "hermes": {
        "label": "Hermes Agent",
        "tools": set(),
        "recognized_keys": {
            "name", "description", "version", "author", "license", "platforms",
            "tags", "category", "required_environment_variables", "prerequisites",
            "compatibility", "environments", "setup", "required_credential_files",
            "related_skills", "metadata",
        },
        "reserved_name_words": set(),
        "bash_tool_names": set(),
        "unknown_tool_severity": "warn",
        "enforces_allowed_tools": False,
        "description_soft_limit": 60,
        "name_pattern": r"[a-z0-9][a-z0-9._-]*",
        "name_charset": (
            "lowercase letters/digits/hyphens/dots/underscores and start with a letter or digit"
        ),
    },
    "openclaw": {
        "label": "OpenClaw",
        "tools": set(),
        "recognized_keys": {
            "name", "description", "allowed-tools", "license", "metadata",
            "homepage", "user-invocable", "disable-model-invocation",
            "command-dispatch", "command-tool", "command-arg-mode",
        },
        "reserved_name_words": set(),
        "bash_tool_names": set(),
        "unknown_tool_severity": "warn",
        "enforces_allowed_tools": False,
        "name_pattern": r"[a-z0-9][a-z0-9-]*",
        "name_charset": "lowercase letters/digits/hyphens and start with a letter or digit",
    },
    "opencode": {
        "label": "OpenCode",
        "tools": set(),
        # OpenCode recognizes only these five keys; unknown frontmatter is
        # silently ignored (https://opencode.ai/docs/skills#write-frontmatter).
        "recognized_keys": {
            "name", "description", "license", "compatibility", "metadata",
        },
        "reserved_name_words": set(),
        "bash_tool_names": set(),
        "unknown_tool_severity": "warn",
        # OpenCode grants tool access through `permission.skill` in
        # opencode.json, not through `allowed-tools`.
        "enforces_allowed_tools": False,
        # Official pattern: 1-64 chars, lowercase alphanumeric with single
        # hyphen separators (no leading/trailing `-`, no `--`, no dots or
        # underscores). Stricter than the general Agent Skills default.
        "name_pattern": r"[a-z0-9]+(-[a-z0-9]+)*",
        "name_charset": (
            "1-64 lowercase letters/digits with single hyphen separators"
        ),
    },
}


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None, None
    end = text.find("\n---", 3)
    if end == -1:
        return None, None
    return text[3:end].lstrip("\n"), text[end + 4:]


_BLOCK_SCALAR = re.compile(r"^([|>])[+-]?[0-9]?[+-]?$")


def get_scalar(fm, key):
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm, re.MULTILINE)
    if not m:
        return None
    value = m.group(1).strip()
    block = _BLOCK_SCALAR.match(value)
    if not block:
        return value.strip('"').strip("'")
    # Block scalar (`key: |` or `key: >`): the value is the indented lines that
    # follow, not the indicator. Reading only the indicator made every block
    # description look one character long, so the 1024-char cap never fired.
    lines = []
    for ln in fm[m.end():].splitlines()[1:]:
        if ln.strip() and not ln[:1].isspace():
            break
        lines.append(ln)
    while lines and not lines[-1].strip():
        lines.pop()
    indent = min((len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()), default=0)
    lines = [ln[indent:] for ln in lines]
    if block.group(1) == "|":
        return "\n".join(lines)
    # Folded (`>`): lines join with a space, blank lines become line breaks.
    return "\n".join(" ".join(p.split("\n")) for p in "\n".join(lines).split("\n\n"))


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


# Plain (unquoted) scalars may not start with these — YAML reserves them.
_RESERVED_PLAIN_START = "@`"
# Values that are not scalars (block scalar, anchor, alias, flow mapping/seq).
_NON_SCALAR_START = "|>&*[{"


def yaml_safety_findings(fm):
    """Flag frontmatter this file's regex parser reads fine but a real YAML
    parser rejects.

    Host loaders (Claude Code, Pi, Copilot CLI) parse frontmatter with a YAML
    parser, so an *unquoted* value containing ': ' is read as a nested mapping
    inside a compact mapping and the whole skill fails to load with
    "Nested mappings are not allowed in compact mappings". Book titles are
    systematically of the form "Title: Subtitle", so a generated description
    hits this constantly — the template quotes the description for exactly
    this reason, and the check keeps that from being written off.

    Dependency-free by design: CI runs this on machines without PyYAML.
    """
    errors, warns = [], []
    for ln in fm.splitlines():
        m = re.match(r"^([A-Za-z][\w-]*):(?:[ \t]+(.*))?$", ln)
        if not m:
            continue
        key, raw = m.group(1), (m.group(2) or "").strip()
        if not raw:
            continue  # `key:` with a nested block / list — handled elsewhere
        if raw[0] in _NON_SCALAR_START:
            continue
        if raw[0] in ("'", '"'):
            q = raw[0]
            closing_escaped = raw[-2:] == ("''" if q == "'" else '\\"')
            if len(raw) < 2 or raw[-1] != q or closing_escaped:
                errors.append(
                    f"frontmatter '{key}': {q}-quoted value is not closed on one "
                    f"line (a multi-line quoted scalar needs indentation on the "
                    f"continuation lines)"
                )
                continue
            inner = raw[1:-1]
            if q == '"' and re.search(r'(?<!\\)"', inner):
                warns.append(
                    f"frontmatter '{key}': unescaped '\"' inside a double-quoted "
                    f"value — escape it as \\\""
                )
            if q == "'" and re.search(r"(?<!')'(?!')", inner):
                warns.append(
                    f"frontmatter '{key}': unescaped \"'\" inside a single-quoted "
                    f"value — escape it as ''"
                )
            continue
        if ": " in raw or raw.endswith(":"):
            errors.append(
                f"frontmatter '{key}': unquoted value contains ': ' — YAML reads "
                f"that as a nested mapping and strict loaders reject the file "
                f"(host skill loading breaks entirely). Wrap the value in double "
                f"quotes: \"{raw[:40]}…\" and escape inner quotes as \\\""
            )
        if raw[0] in _RESERVED_PLAIN_START:
            errors.append(
                f"frontmatter '{key}': plain value starts with reserved YAML "
                f"indicator '{raw[0]}' — quote it"
            )
        if '"' in raw:
            warns.append(
                f"frontmatter '{key}': plain value embeds '\"' — legal today, but "
                f"one edit at the start turns it into a quoted scalar and a parse "
                f"error; quote the whole value"
            )
        if " #" in raw:
            warns.append(
                f"frontmatter '{key}': ' #' in an unquoted value starts a YAML "
                f"comment, so the tail is silently dropped — quote it"
            )
    return errors, warns


def strict_yaml_findings(fm):
    """Parse the frontmatter with PyYAML when it is installed.

    Catches syntax the heuristics above do not model. Silent when PyYAML is
    absent, so the validator keeps its zero-dependency contract.
    """
    try:
        import yaml
    except ImportError:
        return []
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError as exc:
        lines = [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
        head = lines[0] if lines else "invalid YAML"
        where = next((ln for ln in lines[1:] if ln.startswith("in ")), "")
        return [f"frontmatter is not valid YAML: {head} {where}"[:220]]
    if data is not None and not isinstance(data, dict):
        return ["frontmatter does not parse to a YAML mapping"]
    return []


def tool_base(entry):
    """Bash(python3 *) -> Bash ; Read -> Read ; My-MCP(do_thing) -> My-MCP."""
    return entry.split("(", 1)[0].strip()


def audit(path, lens="claude"):
    rules = LENSES[lens]
    label = rules["label"]
    # utf-8-sig so a SKILL.md saved with a UTF-8 BOM still parses — otherwise the
    # leading ﻿ makes text.startswith("---") false and frontmatter is missed.
    text = Path(path).read_text(encoding="utf-8-sig")
    fm, body = parse_frontmatter(text)
    errors, warns = [], []
    if fm is None:
        return ["no valid YAML frontmatter (--- block)"], []

    # A frontmatter block that no YAML parser accepts makes the whole skill
    # unloadable, so these findings lead the report.
    y_errors, y_warns = yaml_safety_findings(fm)
    errors.extend(y_errors)
    warns.extend(y_warns)
    if not y_errors:
        errors.extend(strict_yaml_findings(fm))

    name = get_scalar(fm, "name")
    if not name:
        errors.append("name: missing (required)")
    else:
        if len(name) > 64:
            errors.append(f"name: {len(name)} > 64 chars")
        name_pattern = rules.get("name_pattern", r"[a-z0-9-]+")
        if not re.fullmatch(name_pattern, name):
            charset = rules.get("name_charset", "lowercase letters/digits/hyphens")
            errors.append(f"name: '{name}' must be {charset}")
        for w in rules["reserved_name_words"]:
            if w in name.lower():
                errors.append(f"name: '{name}' contains a reserved word")
                break

    desc = get_scalar(fm, "description")
    if not desc:
        errors.append("description: missing (required)")
    elif len(desc) > 1024:
        errors.append(f"description: {len(desc)} > 1024 chars")
    elif soft_limit := rules.get("description_soft_limit"):
        if len(desc) > soft_limit:
            warns.append(
                f"description: {len(desc)} > {soft_limit} chars "
                f"({label} house guideline for reliable routing)"
            )

    # Tool grant analysis (lens-specific)
    tools = get_list_items(fm, "allowed-tools")
    if not tools:
        inline = get_scalar(fm, "allowed-tools")
        if inline:
            tools = inline.split()
    if tools and rules.get("enforces_allowed_tools", True):
        bases = {tool_base(t) for t in tools}
        known = {b for b in bases if b in rules["tools"]}
        unknown = [t for t in tools if tool_base(t) not in rules["tools"]]
        uses_bash = bool(re.search(r"```bash", body)) or "python3 " in body
        if uses_bash and not (bases & rules["bash_tool_names"]):
            bash_names = " or ".join(f"'{n}'" for n in sorted(rules["bash_tool_names"]))
            errors.append(
                f"allowed-tools declares a restriction but omits {bash_names}, yet the "
                f"skill runs bash/python3 — under {label} those steps would be blocked"
            )
        if not known and rules["tools"]:
            # Claude: hard error (none of the listed tools are recognized).
            # Copilot/Amp: tokens are likely MCP names — handled by the warn path.
            if rules["unknown_tool_severity"] == "error":
                errors.append(f"allowed-tools: no recognized {label} tool in the list")
        if unknown:
            msg = (f"allowed-tools: {unknown} are not {label} built-in tool names "
                   f"(treated as MCP-server names by Copilot, ignored by Claude)")
            if rules["unknown_tool_severity"] == "error":
                # Already covered by the 'no recognized tool' error if list is all-unknown;
                # otherwise it's a soft note.
                warns.append(msg)
            else:
                warns.append(msg)

    for k in top_level_keys(fm):
        if k not in rules["recognized_keys"]:
            warns.append(f"frontmatter '{k}': not a recognized {label} key (ignored by {label})")

    n = len(text.splitlines())
    if n > 500:
        warns.append(f"body: {n} lines > 500 (soft guideline for optimal performance)")

    return errors, warns


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", default="SKILL.md",
                        help="Path to SKILL.md (default: SKILL.md)")
    parser.add_argument("--lens", choices=sorted(LENSES.keys()), default="claude",
                        help="Which host's rules to validate against (default: claude)")
    args = parser.parse_args()

    errors, warns = audit(args.path, lens=args.lens)
    label = LENSES[args.lens]["label"]
    for w in warns:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    if errors:
        print(f"✗ {args.path} [{label}]: {len(errors)} error(s), {len(warns)} warning(s)")
        sys.exit(1)
    print(f"✓ {args.path} [{label}]: no {label}-breaking issues ({len(warns)} warning(s))")


if __name__ == "__main__":
    main()



