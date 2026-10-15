#!/usr/bin/env bash
# End-to-end audit of an existing project that has no standards. It builds a "foreign" project
# (a rendered one without its standard lint config, or a fresh dotnet classlib), plants the stack's
# tests/violations files, commits, runs audit.py tools, and checks every expected rule is found
# while the project stays untouched.
# Usage: scripts/test-audit.sh <standards src> <rendered project> <stack> <work dir>
set -euo pipefail

src="$1" rendered="$2" stack="$3" work="$4"
foreign="$work/foreign $stack" # a space, as real paths have
out="$work/audit-out-$stack"
failed=0
fail() { printf '\033[31mFAIL: audit %s: %s\033[0m\n' "$stack" "$*"; failed=1; }
git_q() { git -c user.email=t@t -c user.name=t -c commit.gpgsign=false -c core.autocrlf=false "$@"; }
rm -rf "$foreign" "$out"
mkdir -p "$foreign"

case "$stack" in
  dotnet)
    (cd "$foreign" && dotnet new classlib -n Legacy -o Legacy >/dev/null &&
      dotnet new sln -n Legacy >/dev/null && dotnet sln add Legacy/Legacy.csproj >/dev/null)
    # The project's own settings must lose to the standard's: warnings-as-errors in the csproj, and
    # a rule the standard enables silenced in its .editorconfig.
    sed -i 's#<PropertyGroup>#<PropertyGroup>\n    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>#' \
      "$foreign/Legacy/Legacy.csproj"
    printf 'root = true\n\n[*.cs]\ndotnet_diagnostic.IDE0161.severity = none\n' >"$foreign/.editorconfig"
    dest="$foreign/Legacy"
    ;;
  typescript | angular)
    tar -C "$rendered" --exclude=node_modules --exclude=.git -cf - . | tar -C "$foreign" -xf -
    rm -f "$foreign/eslint.config.mjs"
    dest="$foreign/src"
    [[ "$stack" == angular ]] && dest="$foreign/src/app"
    ;;
  python)
    tar -C "$rendered" --exclude=.venv --exclude=.git -cf - . | tar -C "$foreign" -xf -
    rm -f "$foreign/ruff.toml"
    dest="$foreign/src/test_python_personal" # the package test-templates renders for python × personal
    ;;
  flutter)
    tar -C "$rendered" --exclude=.dart_tool --exclude=build --exclude=.git -cf - . | tar -C "$foreign" -xf -
    printf '# the project'"'"'s own, before the standards\n' >"$foreign/analysis_options.yaml"
    dest="$foreign/lib"
    ;;
esac

shopt -s nullglob
violations=("$src/tests/violations/$stack"/*.{ts,py,cs,dart})
[[ "$stack" == angular ]] && violations+=("$src/tests/violations/typescript"/*.ts)
shopt -u nullglob
expected=""
for file in "${violations[@]}"; do
  cp "$file" "$dest/"
  expected+=" $(head -n 1 "$file" | sed -E 's/^(\/\/|#) *expect: *//' | tr ',' ' ')"
done
git_q -C "$foreign" init -q
git_q -C "$foreign" add -A
git_q -C "$foreign" commit -qm "legacy project"
state() { git -C "$foreign" status --porcelain; git -C "$foreign" rev-parse HEAD; git -C "$foreign" branch --list; }
before="$(state)"

python3 "$src/scripts/audit.py" tools "$foreign" --stack "$stack" --org personal \
  --render "$rendered" --out "$out" || fail "audit.py exited non-zero"
status="$(jq -r .status "$out/tool-findings.json")"
[[ "$status" == ran* ]] || fail "the tools didn't run: $status"
for id in $expected; do
  rule="$(jq -r --arg id "$id" '[.findings[] | select(.tool_id == $id) | .rule][0] // "missing"' \
    "$out/tool-findings.json")"
  [[ "$rule" != missing && "$rule" != unmapped ]] || fail "$id: $rule"
done
[[ "$(state)" == "$before" ]] || fail "the project changed"
[[ "$(git -C "$foreign" worktree list | wc -l)" -eq 1 ]] || fail "a worktree was left behind"

if [[ "$stack" == python ]]; then
  # Without uv the tools are skipped, never fatal.
  code=0
  PATH=/usr/bin:/bin python3 "$src/scripts/audit.py" tools "$foreign" --stack python --org personal \
    --render "$rendered" --out "$out" || code=$?
  status="$(jq -r .status "$out/tool-findings.json")"
  [[ "$code" == 0 && "$status" == "skipped (uv not found)" ]] || fail "missing uv: exit $code, $status"
fi

rm -rf "$foreign" "$out"
exit "$failed"
