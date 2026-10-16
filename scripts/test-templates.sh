#!/usr/bin/env bash
# Generates every stack x org combination from the working tree, then for each project:
#   1. checks nothing was left unrendered
#   2. runs the project's full check (must pass on a fresh scaffold)
#   3. drops in tests/violations/* and asserts every expected lint rule fires
#
# Usage: scripts/test-templates.sh            # everything
#        STACKS=python ORGS=personal scripts/test-templates.sh
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stacks="${STACKS:-typescript python}"
orgs="${ORGS:-$(find "$root/orgs" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failures=()

copier_cmd() {
  if command -v copier >/dev/null 2>&1; then copier "$@"
  elif command -v uvx >/dev/null 2>&1; then uvx copier "$@"
  else pipx run copier "$@"; fi
}

log() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
fail() { printf '\033[31mFAIL: %s\033[0m\n' "$*"; failures+=("$*"); }

# Snapshot the working tree (uncommitted changes included) without git metadata.
mkdir -p "$work/src"
tar -C "$root" --exclude=.git --exclude=node_modules -cf - . | tar -C "$work/src" -xf -

# A project rule file, as a private copy holds it: must reach that project's AGENTS.md and no other.
mkdir -p "$work/src/orgs/personal/projects"
printf '## Project: fixture

<!-- rules analyzed: 2026-01-01 (none) -->

- **FIX-1 [review]** Fixture rule.
'   >"$work/src/orgs/personal/projects/test-typescript-personal.md"

lint_rule_ids() { # <stack> <project dir> <file> -> one fired rule id per line
  local stack="$1" dir="$2" file="$3"
  if [[ "$stack" == typescript || "$stack" == angular ]]; then
    (cd "$dir" && { npx --no-install eslint --format json "$file" || true; }) |
      jq -r '.[].messages[].ruleId // empty'
  elif [[ "$stack" == flutter ]]; then
    # One line per finding: SEVERITY|TYPE|CODE|file|...; the code is the lint name in capitals.
    (cd "$dir" && { dart analyze --format=machine 2>&1 || true; }) | awk -F'|' 'NF > 3 { print tolower($3) }'
  elif [[ "$stack" == dotnet ]]; then
    # Analyzers, code style and Sonar all report through the build; warnings are errors.
    (cd "$dir" && { dotnet build --nologo 2>&1 || true; }) |
      grep -oE '(error|warning) [A-Z]+[0-9]+' | awk '{print $2}'
  else
    (cd "$dir" && { $RUN ruff check --output-format json "$file" || true; }) | jq -r '.[].code // empty'
  fi
}

check_violations() { # <stack> <org> <project dir> <dest folder for violation files>
  local stack="$1" org="$2" dir="$3" dest="$4" file expected fired rule
  local -a files=()
  shopt -s nullglob
  files+=("$work/src/tests/violations/$stack"/*.{ts,py,cs,dart})
  # Angular projects are TypeScript projects too: every TypeScript rule must fire there as well.
  [[ "$stack" == angular ]] && files+=("$work/src/tests/violations/typescript"/*.ts)
  files+=("$work/src/tests/violations/$stack/$org"/*.{ts,py,cs,dart})
  shopt -u nullglob
  for file in "${files[@]}"; do
    cp "$file" "$dest/"
    local target
    target="$dest/$(basename "$file")"
    expected="$(head -n 1 "$file" | sed -E 's/^(\/\/|#) *expect: *//' | tr ',' '\n' | tr -d ' ')"
    fired="$(lint_rule_ids "$stack" "$dir" "$target" | sort -u)"
    for rule in $expected; do
      if ! grep -qxF "$rule" <<<"$fired"; then
        fail "$stack/$org: rule '$rule' did not fire on $(basename "$file")"
      fi
    done
    rm "$target"
  done
}

check_feature_isolation() { # <dotnet project dir> <root namespace>: a slice that reaches into
  # another feature must fail the architecture tests (VSA-2); the project is clean again afterwards.
  local dir="$1" ns="$2" planted output
  planted="$dir/src/$ns/Features/Orders/PlaceOrder/PlaceOrderHandler.cs"
  mkdir -p "$(dirname "$planted")"
  cat >"$planted" <<EOF
using $ns.Features.Greetings.BuildGreeting;

namespace $ns.Features.Orders.PlaceOrder;

/// <summary>Planted by test-templates.sh: reaches into another feature.</summary>
public sealed class PlaceOrderHandler(BuildGreetingHandler greetings)
{
    /// <summary>Greets the customer.</summary>
    public string Handle(string customer) => greetings.Handle(customer);
}
EOF
  output="$(cd "$dir" && dotnet build --nologo -v q >/dev/null 2>&1 &&
    dotnet test --no-build --output Detailed 2>&1)"
  rm -r "${dir:?}/src/${ns:?}/Features/Orders"
  grep -q 'depends on another feature' <<<"$output"
}

for stack in $stacks; do
  # .NET is generated once per architecture; the other stacks have none ("-").
  architectures="-"
  [[ "$stack" == dotnet ]] && architectures="simple clean vertical-slice"
  for architecture in $architectures; do
  for org in $orgs; do
    name="$stack-$org"
    arch_args=()
    if [[ "$architecture" != - ]]; then
      name="$stack-$architecture-$org"
      arch_args=(--data "architecture=$architecture")
    fi
    dir="$work/$name"
    log "$name: generate"
    copier_cmd copy --trust --defaults --quiet \
      --data project_name="Test $stack $org" --data org="$org" --data stack="$stack" \
      "${arch_args[@]}" --data 'ai_tools=["claude","cursor","copilot"]' \
      "$work/src" "$dir"

    update_workflow="$dir/.github/workflows/ai-standards-update.yml"
    if [[ -f "$update_workflow" ]] && ! grep -q -- '--conflict inline' "$update_workflow"; then
      fail "$name: the update workflow hides conflicts in .rej files"
    fi

    # shellcheck disable=SC2016  # literal ${{ is GitHub Actions syntax, allowed in workflows
    # Angular templates (*.html) use {{ }} themselves, so they are left out.
    if leftovers="$(grep -rn --exclude-dir=node_modules --exclude='*.html' -e '{%' -e '{{' "$dir" | grep -v '\${{')"; then
      fail "$name: unrendered template syntax"; echo "$leftovers"
    fi

    log "$name: install + check"
    if [[ "$stack" == typescript ]]; then
      (cd "$dir" && npm install --no-audit --no-fund --silent)
      (cd "$dir" && npm run --silent check) || fail "$name: npm run check"
      check_violations "$stack" "$org" "$dir" "$dir/src"
      bash "$work/src/scripts/test-hooks.sh" "$dir" "$stack" || fail "$name: hooks"
    elif [[ "$stack" == angular ]]; then
      (cd "$dir" && npm install --no-audit --no-fund --silent)
      (cd "$dir" && npm run --silent check) || fail "$name: npm run check"
      check_violations "$stack" "$org" "$dir" "$dir/src/app"
      bash "$work/src/scripts/test-hooks.sh" "$dir" "$stack" || fail "$name: hooks"
    elif [[ "$stack" == flutter ]]; then
      (cd "$dir" && flutter pub get >/dev/null)
      (cd "$dir" && bash .ai-standards/check.sh) || fail "$name: check.sh"
      check_violations "$stack" "$org" "$dir" "$dir/lib"
      bash "$work/src/scripts/test-hooks.sh" "$dir" "$stack" || fail "$name: hooks"
    elif [[ "$stack" == dotnet ]]; then
      grep -q "^## Architecture" "$dir/AGENTS.md" || fail "$name: no architecture rules in AGENTS.md"
      (cd "$dir" && bash .ai-standards/check.sh) || fail "$name: check.sh"
      first_project="$(cd "$dir" && find src -name '*.csproj' | sort | head -n 1)"
      check_violations "$stack" "$org" "$dir" "$dir/$(dirname "$first_project")"
      bash "$work/src/scripts/test-hooks.sh" "$dir" "$stack" || fail "$name: hooks"
      if [[ "$architecture" == vertical-slice ]]; then
        check_feature_isolation "$dir" "$(basename "$first_project" .csproj)" ||
          fail "$name: VSA-2 not enforced (a cross-feature reference passed the architecture tests)"
      fi
    else
      if command -v uv >/dev/null 2>&1; then
        RUN="uv run"; (cd "$dir" && uv sync --quiet)
      else
        RUN=""; python3 -m venv "$dir/.venv"
        # shellcheck disable=SC1091
        . "$dir/.venv/bin/activate"
        pip install --quiet ruff mypy pytest pytest-cov hatchling && pip install --quiet -e "$dir"
      fi
      (cd "$dir" && make check RUN="$RUN") || fail "$name: make check"
      check_violations "$stack" "$org" "$dir" "$dir/src/test_${stack}_${org//-/_}"
      bash "$work/src/scripts/test-hooks.sh" "$dir" "$stack" || fail "$name: hooks"
      [[ -z "$RUN" ]] && deactivate
    fi

    # Once per stack: audit an existing project that has no standards (scripts/test-audit.sh).
    if [[ "$org" == personal && "$architecture" =~ ^(-|simple)$ ]]; then
      log "$name: audit an existing project without the standards"
      bash "$work/src/scripts/test-audit.sh" "$work/src" "$dir" "$stack" "$work" || fail "$name: audit"
      if [[ "$stack" == python || "$stack" == typescript ]]; then
        bash "$work/src/scripts/test-fix-debt.sh" "$work/src" "$dir" "$stack" "$work" || fail "$name: fix-debt"
      fi
    fi
  done
  done
done

expect() { # <description> <command...>: record a failure if the command fails
  local description="$1"; shift
  "$@" >/dev/null 2>&1 || fail "adopt: $description"
}

log "project layer: a project's rule file reaches only its own AGENTS.md"
if [[ -d "$work/typescript-personal" ]] && ! grep -q 'FIX-1' "$work/typescript-personal/AGENTS.md"; then
  fail "project rules missing from typescript-personal/AGENTS.md"
fi
for other in "$work"/*-example-corp "$work"/python-personal; do
  if [[ -f "$other/AGENTS.md" ]] && grep -q 'FIX-1' "$other/AGENTS.md"; then
    fail "project rules leaked into $(basename "$other")/AGENTS.md"
  fi
done

log "plugin: SessionStart offers onboarding and the periodic rule refresh"
bash "$work/src/scripts/test-session-start.sh" || fail "session-start hook"

log "check_rules.py: no rule written twice inside one org"
python3 "$work/src/scripts/check_rules.py" "$root" >/dev/null || fail "check_rules: the repo itself has duplicates"
# Planted duplicates: the same text (modulo case and punctuation) and the same ID inside one org.
dup="$work/dup-rules"
mkdir -p "$dup" && tar -C "$root" -cf - rules orgs | tar -C "$dup" -xf -
printf '
- **ME-1 [review]** Same text.
' >>"$dup/orgs/personal/rules.md"
mkdir -p "$dup/orgs/personal/projects"
printf '## Project: x

Prose is not a rule.

- **X-1 [review]** Same  text!
- **ME-1 [ai]** Another rule.
'   >"$dup/orgs/personal/projects/x.md"
dup_report="$(python3 "$work/src/scripts/check_rules.py" "$dup" || true)"
grep -q 'duplicate text' <<<"$dup_report" || fail "check_rules: duplicate text not reported"
grep -q 'duplicate id ME-1' <<<"$dup_report" || fail "check_rules: duplicate id not reported"
# The same ID in two different orgs is fine: no project ever sees both.
cross="$work/cross-org-rules"
mkdir -p "$cross" && tar -C "$root" -cf - rules orgs | tar -C "$cross" -xf -
printf '
- **ME-1 [review]** Personal rule.
' >>"$cross/orgs/personal/rules.md"
printf '
- **ME-1 [review]** Corp rule.
' >>"$cross/orgs/example-corp/rules.md"
python3 "$work/src/scripts/check_rules.py" "$cross" >/dev/null || fail "check_rules: same ID in two orgs reported"

log "fresh project: CLAUDE.md imports AGENTS.md exactly once"
fresh="$(find "$work" -maxdepth 1 -name '*-personal' | head -n 1)"
[[ "$(grep -cxF '@AGENTS.md' "$fresh/CLAUDE.md")" == 1 ]] || fail "fresh: @AGENTS.md not imported exactly once"

log "adopt: existing project keeps its own files"
legacy="$work/legacy"
mkdir -p "$legacy"
printf 'My own rules\n- use pnpm\n' >"$legacy/CLAUDE.md"
printf '# Legacy app\n' >"$legacy/README.md"
printf 'node_modules/\n.env\n' >"$legacy/.gitignore"
printf '{"compilerOptions":{"strict":false}}\n' >"$legacy/tsconfig.json"
printf '{"name":"legacy","scripts":{"test":"jest"},"dependencies":{"express":"^4.19.0"}}\n' >"$legacy/package.json"
cp -r "$legacy" "$work/legacy-before"

copier_cmd copy --trust --defaults --quiet --data project_name=legacy --data stack=typescript \
  "$work/src" "$work/legacy-rendered"
python3 "$work/src/scripts/adopt.py" "$work/legacy-rendered" "$legacy" >"$work/adopt-report.txt"

expect "CLAUDE.md starts with the import" test "$(head -n 1 "$legacy/CLAUDE.md")" = "@AGENTS.md"
expect "CLAUDE.md keeps the user's content" grep -qxF -- '- use pnpm' "$legacy/CLAUDE.md"
expect "README untouched" cmp "$legacy/README.md" "$work/legacy-before/README.md"
expect "tsconfig untouched" cmp "$legacy/tsconfig.json" "$work/legacy-before/tsconfig.json"
expect "standard tsconfig saved for review" test -f "$legacy/tsconfig.json.ai-standards"
expect "existing dependency kept" jq -e '.dependencies.express == "^4.19.0"' "$legacy/package.json"
expect "existing script kept" jq -e '.scripts.test == "jest"' "$legacy/package.json"
expect "standard devDependency added" jq -e '.devDependencies.eslint' "$legacy/package.json"
expect "module type not forced on legacy code" jq -e 'has("type") | not' "$legacy/package.json"
expect ".gitignore line not duplicated" test "$(grep -cxF 'node_modules/' "$legacy/.gitignore")" = 1
expect "new files added" test -f "$legacy/eslint.config.mjs" -a -f "$legacy/.copier-answers.yml"
expect "second adopt refuses" grep -q 'already on ai-standards' \
  <(python3 "$work/src/scripts/adopt.py" "$work/legacy-rendered" "$legacy")

for stack in $stacks; do
  # Adopting existing projects is covered for TypeScript and Python; the other stacks come later.
  [[ "$stack" == typescript || "$stack" == python ]] || continue
  log "adopt end to end: $stack (baseline, debt plan, ratchet via copier update)"
  bash "$work/src/scripts/test-adopt.sh" "$work/src" "$work/e2e" "$stack" || fail "adopt e2e: $stack"
done

if ((${#failures[@]})); then
  log "${#failures[@]} failure(s)"; printf ' - %s\n' "${failures[@]}"; exit 1
fi
log "all templates OK"
