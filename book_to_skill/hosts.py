from pathlib import Path
from typing import List

import os


def candidate_roots_for_agent(agent: str) -> List[Path]:
    home = Path.home()
    a = (agent or "").lower()
    if a in ("copilot", "copilot-cli"):
        return [home / ".copilot" / "skills", home / ".agents" / "skills", Path(".github/skills")]
    if a in ("claude", "claude-code", "claude_code"):
        return [home / ".claude" / "skills", Path(".claude/skills")]
    if a in ("amp",):
        return [home / ".agents" / "skills", Path(".agents/skills"), home / ".config" / "agents" / "skills"]
    # Generic / fallback roots
    return [home / ".agents" / "skills", Path(".agents/skills"), Path(".github/skills"), Path(".claude/skills")]
