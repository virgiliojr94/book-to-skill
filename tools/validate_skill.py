#!/usr/bin/env python3
"""Audit a SKILL.md against Agent Skills rules for a chosen host (lens).

Severity:
  ERROR  -> violates the portable skill contract or breaks/degrades the skill
            on the chosen host (fails CI)
  WARN   -> the host ignores it, or it's a soft guideline (does not fail CI)

Lenses:
  claude   — Claude Code rules (default; back-compat)
  copilot  — GitHub Copilot CLI rules
  amp      — Sourcegraph Amp rules
  grok     — Grok Build rules

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
  Grok       https://docs.x.ai/build/features/skills-plugins-marketplaces

Usage: python3 tools/validate_skill.py [--lens claude|copilot|amp|grok] [path/to/SKILL.md]
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

# Grok exposes native snake_case tools and resolves Claude-compatible aliases.
# `allowed-tools` is currently descriptive in Grok rather than an enforced
# permission boundary, so omissions and unknown external/MCP tools remain WARNs.
GROK_TOOLS = {
    "run_terminal_command", "run_terminal_cmd", "read_file", "search_replace",
    "write", "grep", "list_dir", "web_fetch", "web_search", "lsp",
    "ask_user_question", "todo_write", "task", "spawn_subagent",
    "enter_plan_mode", "exit_plan_mode", "get_task_output",
    "get_terminal_command_output", "kill_task", "kill_terminal_command",
    "wait_tasks", "monitor", "image_gen", "image_edit", "deploy_app",
    "image_to_video", "reference_to_video", "scheduler_create",
    "scheduler_delete", "scheduler_list", "skill", "search_tool",
    "Bash", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit",
    "PowerShell", "Grep", "Glob", "LS", "LSP", "WebSearch", "WebFetch",
    "DeployApp", "TodoWrite", "AskUserQuestion", "TaskOutput", "BashOutput",
    "BashOutputTool", "AgentOutputTool", "TaskStop", "KillShell", "KillBash",
    "Skill", "ToolSearch", "Agent", "Task", "EnterPlanMode", "ExitPlanMode",
    "CronCreate", "CronDelete", "CronList", "ListMcpResourcesTool",
}

LENSES = {
    "claude": {
        "label": "Claude Code",
        "tools": CLAUDE_CODE_TOOLS,
        "recognized_keys": {"name", "description", "allowed-tools", "license"},
        "reserved_name_words": {"anthropic", "claude"},
        "bash_tool_names": {"Bash"},
        "case_sensitive_tools": True,
        "missing_shell_severity": "error",
        "unknown_tool_severity": "error",
        "unknown_tool_note": "not recognized by Claude Code",
    },
    "copilot": {
        "label": "GitHub Copilot CLI",
        "tools": COPILOT_CLI_TOOLS,
        "recognized_keys": {"name", "description", "allowed-tools", "license"},
        "reserved_name_words": set(),
        "bash_tool_names": {"shell", "bash"},
        "case_sensitive_tools": True,
        "missing_shell_severity": "error",
        # Unknown tokens are likely MCP server names — Copilot accepts them.
        "unknown_tool_severity": "warn",
        "unknown_tool_note": "may be free-form MCP-server names",
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
        "case_sensitive_tools": True,
        "missing_shell_severity": "error",
        "unknown_tool_severity": "warn",
        "unknown_tool_note": "may refer to external tools",
    },
    "grok": {
        "label": "Grok Build",
        "tools": GROK_TOOLS,
        "recognized_keys": {
            "name", "description", "when-to-use", "when_to_use",
            "allowed-tools", "argument-hint", "user-invocable",
            "disable-model-invocation", "model", "effort", "license",
            "compatibility", "metadata", "paths",
        },
        "reserved_name_words": set(),
        "bash_tool_names": {"run_terminal_command", "run_terminal_cmd", "Bash"},
        # Grok's own docs use lowercase tool examples, while its Claude aliases
        # are capitalized. Advisory validation accepts either casing.
        "case_sensitive_tools": False,
        "missing_shell_severity": "warn",
        "missing_shell_note": (
            "Grok Build currently treats this field as declarative, so the "
            "declaration does not describe the tools used"
        ),
        "unknown_tool_severity": "warn",
        "unknown_tool_note": "may refer to external or MCP tools",
    },
}


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
    """Bash(python3 *) -> Bash ; Read -> Read ; My-MCP(do_thing) -> My-MCP."""
    return entry.split("(", 1)[0].strip()


def split_tool_list(value):
    """Split comma/space-delimited tools, preserving separators inside ()."""
    items, current, depth = [], [], 0
    for char in value:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif depth <= 0 and (char == "," or char.isspace()):
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            current.append(char)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def normalized_tool_name(name, rules):
    return name if rules["case_sensitive_tools"] else name.casefold()


def audit(path, lens="claude"):
    rules = LENSES[lens]
    label = rules["label"]
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
        for w in rules["reserved_name_words"]:
            if w in name.lower():
                errors.append(f"name: '{name}' contains a reserved word")
                break

    desc = get_scalar(fm, "description")
    if not desc:
        errors.append("description: missing (required)")
    elif len(desc) > 1024:
        errors.append(f"description: {len(desc)} > 1024 chars")

    # Tool grant analysis (lens-specific)
    tools = get_list_items(fm, "allowed-tools")
    if not tools:
        inline = get_scalar(fm, "allowed-tools")
        if inline:
            tools = split_tool_list(inline)
    if tools:
        bases = {normalized_tool_name(tool_base(t), rules) for t in tools}
        known_tools = {
            normalized_tool_name(tool, rules) for tool in rules["tools"]
        }
        shell_tools = {
            normalized_tool_name(tool, rules)
            for tool in rules["bash_tool_names"]
        }
        known = bases & known_tools
        unknown = [
            t for t in tools
            if normalized_tool_name(tool_base(t), rules) not in known_tools
        ]
        uses_bash = bool(re.search(r"```bash", body)) or "python3 " in body
        if uses_bash and not (bases & shell_tools):
            bash_names = " or ".join(f"'{n}'" for n in sorted(rules["bash_tool_names"]))
            if rules["missing_shell_severity"] == "error":
                errors.append(
                    f"allowed-tools declares a restriction but omits {bash_names}, yet the "
                    f"skill runs bash/python3 — under {label} those steps would be blocked"
                )
            else:
                warns.append(
                    f"allowed-tools omits {bash_names}, yet the skill runs bash/python3; "
                    f"{rules['missing_shell_note']}"
                )
        if not known and rules["tools"]:
            if rules["unknown_tool_severity"] == "error":
                errors.append(f"allowed-tools: no recognized {label} tool in the list")
        if unknown:
            msg = (f"allowed-tools: {unknown} are not {label} built-in tool names "
                   f"({rules['unknown_tool_note']})")
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
