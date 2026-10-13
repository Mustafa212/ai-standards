#!/usr/bin/env bash
# Runs at the start of every Claude Code session, in every project.
# Whatever this prints is added to Claude's context, so the standards apply
# even when nobody remembers to mention them.
set -uo pipefail

# A registered project's rules are re-analyzed once the code has moved on this much since the
# last analysis (the "rules analyzed: <date> (<sha>)" line in AGENTS.md).
REFRESH_DAYS=30
REFRESH_COMMITS=10

project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
# Windows (Git Bash): turn C:\Users\... into /c/Users/... so file tests work.
command -v cygpath >/dev/null 2>&1 && project_dir="$(cygpath -u "$project_dir")"
answers="$project_dir/.copier-answers.yml"
source_hint="${CLAUDE_PLUGIN_OPTION_STANDARDS_SOURCE:-}"
# Claude Code passes {"source": "startup|clear|compact", ...} on stdin.
hook_input=""
[[ -t 0 ]] || hook_input="$(cat)"
compacted=false
grep -qE '"source" *: *"compact"' <<<"$hook_input" && compacted=true

read_answer() { # <key>: value of a top-level key in .copier-answers.yml
  sed -n "s/^$1: *//p" "$answers" | head -n 1 | tr -d "'\""
}

days_since() { # <YYYY-MM-DD>: whole days from that date until today (GNU date, else BSD date)
  local epoch
  epoch="$(date -d "$1" +%s 2>/dev/null || date -j -f %Y-%m-%d "$1" +%s 2>/dev/null)" || return 1
  echo $((($(date +%s) - epoch) / 86400))
}

commits_since() { # <sha or none>: commits since that one; every commit if it's none or unknown
  if [[ "$1" != none ]] && git -C "$project_dir" rev-list --count "$1..HEAD" 2>/dev/null; then
    return 0
  fi
  git -C "$project_dir" rev-list --count HEAD 2>/dev/null
}

refresh_due() { # <date> <sha or none>: succeeds when the project rules should be re-analyzed
  local days commits
  days="$(days_since "$1")" || return 1
  ((days >= REFRESH_DAYS)) || return 1
  commits="$(commits_since "$2")" || return 1
  ((commits >= REFRESH_COMMITS))
}

if [[ -f "$answers" ]]; then
  org="$(read_answer org)"
  stack="$(read_answer stack)"
  commit="$(read_answer _commit)"
  cat <<EOF
[ai-standards] This project follows ai-standards (org: ${org:-?}, stack: ${stack:-?}, version: ${commit:-unknown}).
- AGENTS.md holds the rules. Follow them; [tool] rules are enforced by lint/CI and hooks.
- Never edit managed files (lint configs, CI, AGENTS.md) to get checks passing; fix the code.
- Never apply a standards change (update, new or changed rule, promotion to the org, refresh)
  without asking the user first and getting a clear yes.
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
  marker="$(grep -m 1 -oE 'rules analyzed: [0-9]{4}-[0-9]{2}-[0-9]{2} \((none|[0-9a-f]+)\)' \
    "$project_dir/AGENTS.md" 2>/dev/null)"
  if [[ "$compacted" == false && "$marker" =~ ([0-9-]{10})\ \((none|[0-9a-f]+)\) ]] &&
    refresh_due "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"; then
    cat <<EOF
- The project rules were last analyzed on ${BASH_REMATCH[1]}, and the code has moved on since. At the
  end of your first reply, add ONE short line offering to refresh them with the ai-standards:onboard
  skill (refresh mode: only what changed; nothing is saved without the user's OK). Don't repeat it.
EOF
  fi
  exit 0
fi

# The user opted out of onboarding offers for this project.
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
ai-standards:onboard skill (it asks which org the project belongs to, registers it, then scaffolds)
before writing any code or config by hand. Do not hand-write lint, formatter, CI or
tsconfig/pyproject files; the template provides them.${source_hint:+ Template source: $source_hint.}
EOF
elif [[ -f "$project_dir/package.json" || -f "$project_dir/pyproject.toml" || -f "$project_dir/requirements.txt" ]]; then
  # After a compaction the offer was already made in this session; don't repeat it.
  [[ "$compacted" == true ]] && exit 0
  cat <<EOF
[ai-standards] This existing project is not on ai-standards yet (no .copier-answers.yml).
At the end of your first reply in this session, add ONE short line offering to register it with the
ai-standards:onboard skill: it asks which org the project belongs to, audits first (nothing is
overwritten), and proposes project rules from the code for the user's OK. Don't repeat the offer in
this session. If the user says no for good, offer to create an empty .ai-standards-skip file so it
never asks again. Do the user's actual request first; never start onboarding without their OK.
EOF
else
  cat <<EOF
[ai-standards] This existing project is not on ai-standards, and its stack has no template yet.
Mention ai-standards only if the user asks about standards or project setup.
EOF
fi
exit 0
