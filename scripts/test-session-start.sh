#!/usr/bin/env bash
# Exercises the plugin's SessionStart hook on small fixture folders: when it offers onboarding,
# and when it offers to refresh a registered project's rules (30 days and 10 commits since the
# last analysis). Usage: scripts/test-session-start.sh   (prints FAIL lines, exits non-zero on any)
set -uo pipefail

hook="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/plugin/hooks/session-start.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failures=0
fail() { printf '\033[31mFAIL: session-start: %s\033[0m\n' "$*"; failures=$((failures + 1)); }
git_q() { git -c user.email=t@t -c user.name=t -c commit.gpgsign=false -c core.autocrlf=false "$@"; }

make_commits() { # <dir> <count>: add that many commits (creating the repo if needed)
  [[ -d "$1/.git" ]] || git init -q "$1"
  for n in $(seq 1 "$2"); do
    echo "$n" >>"$1/counter.txt"
    git_q -C "$1" add counter.txt && git_q -C "$1" commit -qm "chore: commit $n"
  done
}

register() { # <dir> <analysis date> <sha or none>: make the folder look like an onboarded project
  mkdir -p "$1"
  printf '_commit: v0.4.0\norg: personal\nstack: typescript\n' >"$1/.copier-answers.yml"
  printf '## Project: fixture\n\n<!-- repo: x · stack: typescript · rules analyzed: %s (%s) -->\n' \
    "$2" "$3" >"$1/AGENTS.md"
}

hook_output() { CLAUDE_PROJECT_DIR="$1" bash "$hook" </dev/null; }

expect_refresh() { # <description> <dir> <yes|no>
  local output
  output="$(hook_output "$2")" || fail "$1: hook exited non-zero"
  if [[ "$3" == yes ]] && ! grep -q 'offering to refresh' <<<"$output"; then fail "$1: no refresh offer"; fi
  if [[ "$3" == no ]] && grep -q 'offering to refresh' <<<"$output"; then fail "$1: unexpected refresh offer"; fi
}

old="$(date -d '40 days ago' +%F)"
today="$(date +%F)"

dir="$work/due"
make_commits "$dir" 1
register "$dir" "$old" "$(git -C "$dir" rev-parse --short HEAD)"
make_commits "$dir" 12
expect_refresh "40 days old, 12 commits since" "$dir" yes

dir="$work/fresh"
make_commits "$dir" 12
register "$dir" "$today" "$(git -C "$dir" rev-parse --short HEAD~11)"
expect_refresh "analyzed today" "$dir" no

dir="$work/rebased"
make_commits "$dir" 12
register "$dir" "$old" "deadbee"
expect_refresh "sha no longer in history (counts every commit)" "$dir" yes

dir="$work/new-project"
make_commits "$dir" 3
register "$dir" "$old" none
expect_refresh "new project, only 3 commits" "$dir" no

dir="$work/not-git"
register "$dir" "$old" none
expect_refresh "not a git repository" "$dir" no

dir="$work/unregistered"
mkdir -p "$dir" && echo '{}' >"$dir/package.json"
grep -q 'ai-standards:onboard' <<<"$(hook_output "$dir")" || fail "existing project: no onboard offer"

dir="$work/empty"
mkdir -p "$dir"
grep -q 'ai-standards:onboard' <<<"$(hook_output "$dir")" || fail "empty folder: onboard not required"

exit $((failures > 0))
