#!/usr/bin/env bash
# Exercises the plugin's SessionStart hook on small fixture folders: when it offers onboarding,
# and when it offers to refresh a registered project's rules (7 days and 5 commits since the
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

# A project registered in the second of two private copies but not adopted: summary of its latest
# report, and the refresh offer once it's due.
home="$work/ai-home"
clone="$home/clone"
mkdir -p "$home/other/orgs/acme/projects" "$clone/orgs/personal/projects" "$home/reports/personal/fixture-app"
printf '## Project: other\n\n<!-- repo: https://example.com/acme/other -->\n' >"$home/other/orgs/acme/projects/other.md"
printf 'Source: gh:x/other\nClone: %s\nSource: gh:x/y\nClone: %s\n' "$home/other" "$clone" >"$home/config.md"
dir="$work/registered"
make_commits "$dir" 1
git -C "$dir" remote add origin "https://someone@example.com/acme/fixture-app.git"
printf '## Project: fixture\n\n<!-- prefix: FIX · repo: https://example.com/acme/fixture-app · stack: dotnet · rules analyzed: %s (%s) -->\n' \
  "$old" "$(git -C "$dir" rev-parse --short HEAD)" >"$clone/orgs/personal/projects/fixture-app.md"
make_commits "$dir" 6
printf '**212 findings** in 9 areas — P1 23 · P2 41 · P3 88 · P4 60\n' \
  >"$home/reports/personal/fixture-app/STANDARDS-DEBT.md"
output="$(AI_STANDARDS_HOME="$home" hook_output "$dir")"
grep -q '212 findings, P1 23' <<<"$output" || fail "registered project: no report summary"
grep -q 'offering to refresh' <<<"$output" || fail "registered project: no refresh offer (40 days, 6 commits)"
grep -q 'not on ai-standards yet' <<<"$output" && fail "registered project: offered onboarding again"
grep -q 'no rendered rules yet' <<<"$output" || fail "registered project: no hint that the audit renders the rules"
printf '# rules in effect\n' >"$home/reports/personal/fixture-app/RULES.md"
output="$(AI_STANDARDS_HOME="$home" hook_output "$dir")"
grep -q 'fixture-app/RULES.md' <<<"$output" || fail "registered project: the rendered rules file isn't named"

recent="$(date -d '3 days ago' +%F)"
sed -i "s/rules analyzed: [0-9-]*/rules analyzed: $recent/" "$clone/orgs/personal/projects/fixture-app.md"
output="$(AI_STANDARDS_HOME="$home" hook_output "$dir")"
grep -q 'offering to refresh' <<<"$output" && fail "registered project: refresh offered after 3 days"

for case in "dotnet-nested:backend/App.sln" "angular:angular.json" "flutter:pubspec.yaml"; do
  dir="$work/${case%%:*}"
  mkdir -p "$dir/$(dirname "${case#*:}")" && echo '{}' >"$dir/${case#*:}"
  grep -q 'ai-standards:onboard' <<<"$(AI_STANDARDS_HOME="$home" hook_output "$dir")" ||
    fail "${case%%:*}: no onboard offer"
done

exit $((failures > 0))
