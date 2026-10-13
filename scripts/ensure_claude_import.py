"""Make sure the project's CLAUDE.md imports AGENTS.md, without touching anything else in it.

CLAUDE.md belongs to the project owner. The only thing ai-standards needs from it is the
`@AGENTS.md` line, so Claude Code reads the shared standards. Idempotent.

Usage: python ensure_claude_import.py <project-dir>
"""

import sys
from pathlib import Path

IMPORT_LINE = "@AGENTS.md"


def ensure_import(project_dir: Path) -> str:
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text(f"{IMPORT_LINE}\n", encoding="utf-8")
        return "created CLAUDE.md with the AGENTS.md import"

    content = claude_md.read_text(encoding="utf-8")
    if any(line.strip() == IMPORT_LINE for line in content.splitlines()):
        return "CLAUDE.md already imports AGENTS.md"

    claude_md.write_text(f"{IMPORT_LINE}\n\n{content}", encoding="utf-8")
    return "added the AGENTS.md import to the top of CLAUDE.md (rest unchanged)"


if __name__ == "__main__":
    print(f"[ai-standards] {ensure_import(Path(sys.argv[1]))}")
