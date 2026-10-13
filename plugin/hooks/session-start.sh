#!/usr/bin/env bash
# Runs at the start of every Claude Code session, in every project.
# Whatever this prints is added to Claude's context, so the standards apply
# even when nobody remembers to mention them.
set -uo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
answers="$project_dir/.copier-answers.yml"
source_hint="${CLAUDE_PLUGIN_OPTION_STANDARDS_SOURCE:-}"

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
  exit 0
fi

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
else
  cat <<EOF
[ai-standards] This existing project is not on ai-standards yet (no .copier-answers.yml).
Do not mention this unless the user asks about standards, linting, CI or project setup; then offer
to adopt the standards with the ai-standards:init-project skill (adopt mode).
EOF
fi
exit 0
