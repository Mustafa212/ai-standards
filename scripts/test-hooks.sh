#!/usr/bin/env bash
# Exercises the Claude Code hooks of a generated, installed project.
# Usage: scripts/test-hooks.sh <project dir> <typescript|python|dotnet>
# Prints FAIL lines and exits non-zero on any failure.
set -uo pipefail

dir="$1"
stack="$2"
failures=0
fail() { printf '\033[31mFAIL: hooks/%s: %s\033[0m\n' "$stack" "$*"; failures=$((failures + 1)); }

# shellcheck disable=SC2034  # check/protect are read through the nameref in hook()
if [[ "$stack" == dotnet ]]; then
  check=(bash .claude/hooks/check-edited-file.sh)
  protect=(bash .claude/hooks/protect-managed-files.sh)
elif [[ "$stack" == typescript ]]; then
  check=(node .claude/hooks/check-edited-file.mjs)
  protect=(node .claude/hooks/protect-managed-files.mjs)
  ext=ts
  # A literal assigned straight to a const counts as named, so pass it through a call instead.
  legacy_line='export const legacyTimeout = Number(86400);'
  new_line='export const newTimeout = Number(3600);'
  expected_rule='no-magic-numbers'
else
  # Same interpreter the generated settings.json uses (the project venv, which has ruff).
  if command -v uv >/dev/null 2>&1; then py=(uv run --quiet python); else py=(python3); fi
  check=("${py[@]}" .claude/hooks/check_edited_file.py)
  protect=("${py[@]}" .claude/hooks/protect_managed_files.py)
  ext=py
  legacy_line='LEGACY_TIMEOUT = print(86400)'
  new_line='NEW_TIMEOUT = print(3600)'
  expected_rule='T201'
fi
code_dir="src"
[[ "$stack" == dotnet ]] && code_dir="$(dirname "$(cd "$dir" && find src -name '*.csproj' | head -n 1)")"
[[ "$stack" == python ]] && code_dir="src/$(basename "$(find "$dir/src" -mindepth 1 -maxdepth 1 -type d | head -n 1)")"

# shellcheck disable=SC2034  # check/protect are used through the nameref in hook()
hook() { # <hook command array name> <relative file> -> sets $hook_exit and $hook_err
  local -n command="$1"
  local payload
  payload="{\"tool_input\":{\"file_path\":\"$dir/$2\"}}"
  hook_err="$(cd "$dir" && printf '%s' "$payload" | CLAUDE_PROJECT_DIR="$dir" "${command[@]}" 2>&1 >/dev/null)"
  hook_exit=$?
}

# .NET: the edit hook only formats (analyzers run in the build), and both hooks are plain bash.
if [[ "$stack" == dotnet ]]; then
  hook protect "Directory.Build.props"
  [[ $hook_exit == 2 ]] || fail "edit to managed Directory.Build.props not blocked"
  hook protect "CLAUDE.md"
  [[ $hook_exit == 0 ]] || fail "edit to project-owned CLAUDE.md was blocked: $hook_err"
  hook protect "$code_dir/Program.cs"
  [[ $hook_exit == 0 ]] || fail "edit to source file was blocked: $hook_err"
  # A relative path, as some tools send it, is matched the same way.
  relative_err="$(cd "$dir" && printf '{"tool_input":{"file_path":"global.json"}}' |
    CLAUDE_PROJECT_DIR="$dir" bash .claude/hooks/protect-managed-files.sh 2>&1)"
  grep -q 'Blocked' <<<"$relative_err" || fail "relative path to managed global.json not blocked"

  unformatted='namespace Demo;
public static class Spacing
{
        public static int One()   =>   1;
}
'
  printf '%b' "$unformatted" >"$dir/$code_dir/Spacing.cs"
  cp "$dir/$code_dir/Spacing.cs" "$dir/unformatted.cs.txt"
  hook check "$code_dir/Spacing.cs"
  [[ $hook_exit == 0 ]] || fail "check hook failed (exit $hook_exit): $hook_err"
  cmp -s "$dir/$code_dir/Spacing.cs" "$dir/unformatted.cs.txt" && fail "edited C# file was not formatted"

  mkdir -p "$dir/.ai-session"
  printf '%b' "$unformatted" >"$dir/.ai-session/Scratch.cs"
  hook check ".ai-session/Scratch.cs"
  cmp -s "$dir/.ai-session/Scratch.cs" "$dir/unformatted.cs.txt" || fail ".ai-session file was formatted"

  rm -rf "$dir/.ai-session" "$dir/$code_dir/Spacing.cs" "$dir/unformatted.cs.txt"
  exit $((failures > 0))
fi

(
  cd "$dir" || exit 1
  git init -q 2>/dev/null
  git add -A && git -c user.email=t@t -c user.name=t commit -qm "chore: base" --no-verify
) || fail "could not create base commit"

# A legacy file with an existing violation, committed.
printf '%s\n' "$legacy_line" >"$dir/$code_dir/legacy.$ext"
(cd "$dir" && git add -A && git -c user.email=t@t -c user.name=t commit -qm "chore: legacy" --no-verify)

hook check "$code_dir/legacy.$ext"
[[ $hook_exit == 0 ]] || fail "untouched legacy violation was reported: $hook_err"

printf '%s\n' "$new_line" >>"$dir/$code_dir/legacy.$ext"
hook check "$code_dir/legacy.$ext"
[[ $hook_exit == 2 ]] || fail "new violation in tracked file not reported (exit $hook_exit)"
grep -q ':2:' <<<"$hook_err" || fail "new violation not reported on line 2: $hook_err"
grep -q ':1:' <<<"$hook_err" && fail "legacy line 1 reported along with the new one: $hook_err"
grep -q "$expected_rule" <<<"$hook_err" || fail "expected rule $expected_rule missing: $hook_err"
grep -q 'legacyTimeout\|LEGACY_TIMEOUT' "$dir/$code_dir/legacy.$ext" || fail "legacy line was rewritten"

printf '%s\n' "$new_line" >"$dir/$code_dir/brand_new.$ext"
hook check "$code_dir/brand_new.$ext"
[[ $hook_exit == 2 ]] || fail "violation in new file not reported (exit $hook_exit)"

mkdir -p "$dir/.ai-session/tests"
printf '%s\n' "$new_line" >"$dir/.ai-session/tests/scratch.$ext"
hook check ".ai-session/tests/scratch.$ext"
[[ $hook_exit == 0 ]] || fail ".ai-session file was linted: $hook_err"

if [[ "$stack" == typescript ]]; then managed="eslint.config.mjs"; else managed="ruff.toml"; fi
hook protect "$managed"
[[ $hook_exit == 2 ]] || fail "edit to managed $managed not blocked"
hook protect "CLAUDE.md"
[[ $hook_exit == 0 ]] || fail "edit to project-owned CLAUDE.md was blocked"
hook protect "$code_dir/legacy.$ext"
[[ $hook_exit == 0 ]] || fail "edit to source file was blocked"

rm -rf "$dir/.ai-session" "$dir/$code_dir/brand_new.$ext"
(cd "$dir" && git checkout -q -- . && git reset -q --hard HEAD~1)
exit $((failures > 0))
