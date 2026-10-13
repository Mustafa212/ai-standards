#!/usr/bin/env bash
# Runs at the start of every Claude Code session, in every project.
# Whatever this prints is added to Claude's context, so the standards apply
# even when nobody remembers to mention them.
set -uo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
# Windows (Git Bash): turn C:\Users\... into /c/Users/... so file tests work.
command -v cygpath >/dev/null 2>&1 && project_dir="$(cygpath -u "$project_dir")"
answers="$project_dir/.copier-answers.yml"
source_hint="${CLAUDE_PLUGIN_OPTION_STANDARDS_SOURCE:-}"
# Claude Code passes {"source": "startup|clear|compact", ...} on stdin.
hook_input=""
[[ -t 0 ]] || hook_input="$(cat)"

read_answer() {
  sed -n "s/^$1: *//p" "$answers" | head -n 1 | tr -d "'\""
}

if [[ -f "$answers" ]]; then
  org="$(read_answer org)"
  stack="$(read_answer stack)"
  commit="$(read_answer _commit)"
  cat <<EOF
[ai-standards] This project follows ai-standards (org: ${org:-?}, stack: ${stack:-?}, version: ${commit:-unknown}).
- AGENTS.md holds the rules. Follow them; [tool] rules are enforced by lint/CI and hooks.
- Never edit managed files (lint configs, CI, AGENTS.md) to get checks passing; fix the code.
- If the user asks to update the standards, use the ai-standards:update-standards skill.
- If you or the user notice the same problem twice, offer the ai-standards:propose-rule skill.
EOF
  debt="$project_dir/docs/STANDARDS-DEBT.md"
  if [[ -f "$debt" ]]; then
    summary="$(grep -m 1 -oE '[0-9]+ baselined findings? in [0-9]+ files?' "$debt")"
    cat <<EOF
- Adopted project with existing debt (${summary:-see docs/STANDARDS-DEBT.md}). New and changed lines must be clean;
  never fix old debt inside feature work (ADOPT-2). When the user wants to pay it down, use the
  ai-standards:fix-debt skill.
EOF
  fi
  exit 0
fi

# The user opted out of adoption offers for this project.
[[ -f "$project_dir/.ai-standards-skip" ]] && exit 0

# Anything besides git metadata, editor folders and docs counts as existing code.
existing_files="$(find "$project_dir" -mindepth 1 -maxdepth 1 \
  ! -name '.git' ! -name '.claude' ! -name '.vscode' ! -name '.idea' \
  ! -name '.DS_Store' ! -iname 'README*' ! -iname 'LICENSE*' ! -name '*.md' \
  2>/dev/null | head -n 1)"

if [[ -z "$existing_files" ]]; then
  cat <<EOF
[ai-standards] This directory has no project yet.
REQUIRED: when the user asks to create, start, init or scaffold a project here, you MUST use the
ai-standards:init-project skill before writing any code or config by hand. Do not hand-write lint,
formatter, CI or tsconfig/pyproject files; the template provides them.${source_hint:+ Template source: $source_hint.}
EOF
elif [[ -f "$project_dir/package.json" || -f "$project_dir/pyproject.toml" || -f "$project_dir/requirements.txt" ]]; then
  # After a compaction the offer was already made in this session; don't repeat it.
  grep -qE '"source" *: *"compact"' <<<"$hook_input" && exit 0
  cat <<EOF
[ai-standards] This existing project is not on ai-standards yet (no .copier-answers.yml).
At the end of your first reply in this session, add ONE short line offering to audit it and bring it
onto the standards with the ai-standards:adopt-project skill (audit first; nothing is overwritten;
old code is baselined, new code is checked). Don't repeat the offer in this session. If the user
says no for good, offer to create an empty .ai-standards-skip file so it never asks again.
Do the user's actual request first; never start adopting without their OK.
EOF
else
  cat <<EOF
[ai-standards] This existing project is not on ai-standards, and its stack has no template yet.
Mention ai-standards only if the user asks about standards or project setup.
EOF
fi
exit 0
