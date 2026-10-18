#!/usr/bin/env bash
# Generates every stack x org combination from the working tree, then for each project:
#   1. checks nothing was left unrendered
#   2. runs the project's full check (must pass on a fresh scaffold)
#   3. drops in tests/violations/* and asserts every expected lint rule fires
#
# Usage: scripts/test-templates.sh            # everything
#        STACKS=python ORGS=personal scripts/test-templates.sh
#        STACKS=workspace scripts/test-templates.sh   # a repo root with a .NET and an Angular folder
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
  grep -q 'depends on another feature' <<<"$output" || return 1
  # VSA-7: Domain/ that reaches into a feature must fail too.
  planted="$dir/src/$ns/Domain/Greetings/Greeting.cs"
  mkdir -p "$(dirname "$planted")"
  cat >"$planted" <<EOF
using $ns.Features.Greetings.BuildGreeting;

namespace $ns.Domain.Greetings;

/// <summary>Planted by test-templates.sh: the domain reaches into a feature.</summary>
public sealed record Greeting(BuildGreetingHandler Handler);
EOF
  output="$(cd "$dir" && dotnet build --nologo -v q >/dev/null 2>&1 &&
    dotnet test --no-build --output Detailed 2>&1)"
  rm -r "${dir:?}/src/${ns:?}/Domain"
  grep -q 'depends on a feature' <<<"$output"
}

check_module_boundaries() { # <dotnet project dir> <root namespace>: a public type inside a module
  # (MOD-2) and a module that uses another module's implementation (MOD-1) must each fail the
  # architecture tests; the project is clean again afterwards.
  local dir="$1" ns="$2" leak orders output
  leak="$dir/src/$ns.Modules.Greetings/Leak.cs"
  printf 'namespace %s.Modules.Greetings;\n\n/// <summary>Planted by test-templates.sh: public inside a module.</summary>\npublic sealed record Leak(string Value);\n' "$ns" >"$leak"
  output="$(cd "$dir" && dotnet build --nologo -v q >/dev/null 2>&1 &&
    dotnet test --no-build --output Detailed 2>&1)"
  rm "$leak"
  grep -q 'makes types public' <<<"$output" || return 1
  orders="$dir/src/$ns.Modules.Orders"
  mkdir -p "$orders"
  cat >"$orders/$ns.Modules.Orders.csproj" <<EOF
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <ProjectReference Include="../$ns.Modules.Greetings/$ns.Modules.Greetings.csproj" />
  </ItemGroup>
</Project>
EOF
  cat >"$orders/OrdersModule.cs" <<EOF
using Microsoft.Extensions.DependencyInjection;
using $ns.Modules.Greetings;

namespace $ns.Modules.Orders;

/// <summary>Planted by test-templates.sh: uses the Greetings module's implementation.</summary>
public static class OrdersModule
{
    /// <summary>Adds the Greetings module itself instead of asking for its Contracts.</summary>
    public static IServiceCollection AddOrdersModule(this IServiceCollection services) => services.AddGreetingsModule();
}
EOF
  cp "$dir/src/$ns.Host/$ns.Host.csproj" "$dir/host.csproj.bak"
  cp "$dir/$ns.slnx" "$dir/slnx.bak"
  output="$(cd "$dir" && dotnet sln add "src/$ns.Modules.Orders/$ns.Modules.Orders.csproj" >/dev/null &&
    dotnet add "src/$ns.Host/$ns.Host.csproj" reference "src/$ns.Modules.Orders/$ns.Modules.Orders.csproj" >/dev/null &&
    dotnet build --nologo -v q >/dev/null 2>&1 && dotnet test --no-build --output Detailed 2>&1)"
  mv "$dir/host.csproj.bak" "$dir/src/$ns.Host/$ns.Host.csproj"
  mv "$dir/slnx.bak" "$dir/$ns.slnx"
  rm -r "${orders:?}"
  grep -q "uses another module's implementation" <<<"$output"
}

check_use_case_isolation() { # <dotnet project dir> <root namespace>: a use case that calls another
  # must fail the architecture tests (CLEAN-10), and one whose name starts with another's must not.
  local dir="$1" ns="$2" app="$1/src/$2.Application/Features" output
  mkdir -p "$app/Orders/PlaceOrder" "$app/Greetings/BuildGreetingTwice"
  cat >"$app/Orders/PlaceOrder/PlaceOrderHandler.cs" <<EOF
using $ns.Application.Features.Greetings.BuildGreeting;

namespace $ns.Application.Features.Orders.PlaceOrder;

/// <summary>Planted by test-templates.sh: calls another use case.</summary>
public sealed class PlaceOrderHandler(BuildGreetingHandler greetings)
{
    /// <summary>The use case it calls.</summary>
    public BuildGreetingHandler Greetings => greetings;
}
EOF
  output="$(cd "$dir" && dotnet build --nologo -v q >/dev/null 2>&1 &&
    dotnet test --no-build --output Detailed 2>&1)"
  rm -r "${app:?}/Orders"
  grep -q 'depends on another use case' <<<"$output" || return 1
  cat >"$app/Greetings/BuildGreetingTwice/BuildGreetingTwiceHandler.cs" <<EOF
namespace $ns.Application.Features.Greetings.BuildGreetingTwice;

/// <summary>Planted by test-templates.sh: its name starts with another use case's.</summary>
public sealed class BuildGreetingTwiceHandler(BuildGreetingTwiceRules rules)
{
    /// <summary>Its own helper.</summary>
    public BuildGreetingTwiceRules Rules => rules;
}
EOF
  cat >"$app/Greetings/BuildGreetingTwice/BuildGreetingTwiceRules.cs" <<EOF
namespace $ns.Application.Features.Greetings.BuildGreetingTwice;

/// <summary>Planted by test-templates.sh: a helper of the same use case.</summary>
public sealed record BuildGreetingTwiceRules(string Separator);
EOF
  output="$(cd "$dir" && dotnet build --nologo -v q >/dev/null 2>&1 &&
    dotnet test --no-build --output Detailed 2>&1)"
  rm -r "${app:?}/Greetings/BuildGreetingTwice"
  ! grep -q 'depends on another use case' <<<"$output"
}

settings_blocks() { # <workspace root> <file>: true when a PreToolUse command of the root's
  # settings.json blocks (exit 2) an edit of the file, run the way Claude Code runs it.
  local command code
  while IFS= read -r command; do
    code=0
    (cd "$1" && printf '{"tool_input":{"file_path":"%s"}}' "$1/$2" |
      CLAUDE_PROJECT_DIR="$1" bash -c "$command" >/dev/null 2>&1) || code=$?
    ((code == 2)) && return 0
  done < <(python3 -c 'import json, sys
for group in json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]["PreToolUse"]:
    print("\n".join(hook["command"] for hook in group["hooks"]))' "$1/.claude/settings.json" | tr -d '\r')
  return 1
}

check_workspace() { # a repo whose root is a workspace (pre-commit, CI, Claude settings) and whose
  # folders are projects rendered with in_workspace=true: the root's tools must reach every folder.
  local ws="$work/workspace" found leftovers out spacing
  local tools=(--data 'ai_tools=["claude","cursor","copilot"]')
  log "workspace: generate the root, backend/ (dotnet) and frontend/ (angular)"
  copier_cmd copy --trust --defaults --quiet --data project_name="Test workspace" --data stack=workspace \
    --data 'workspace_projects={backend: dotnet, frontend: angular}' "${tools[@]}" "$work/src" "$ws"
  copier_cmd copy --trust --defaults --quiet --data project_name="Test backend" --data stack=dotnet \
    --data in_workspace=true "${tools[@]}" "$work/src" "$ws/backend"
  copier_cmd copy --trust --defaults --quiet --data project_name="Test frontend" --data stack=angular \
    --data in_workspace=true "${tools[@]}" "$work/src" "$ws/frontend"
  for found in {backend,frontend}/{.pre-commit-config.yaml,.github,.claude/settings.json}; do
    [[ -e "$ws/$found" ]] && fail "workspace: $found is rendered, but only the root's is read"
  done
  # shellcheck disable=SC2016  # literal ${{ is GitHub Actions syntax
  if leftovers="$(grep -rn --exclude='*.html' -e '{%' -e '{{' "$ws" | grep -v '\${{')"; then
    fail "workspace: unrendered template syntax"; echo "$leftovers"
  fi

  log "workspace: each project's full check, from its folder"
  (cd "$ws/backend" && bash .ai-standards/check.sh) || fail "workspace: backend check.sh"
  (cd "$ws/frontend" && npm install --no-audit --no-fund --silent && npm run --silent check) ||
    fail "workspace: frontend npm run check"

  log "workspace: pre-commit at the root runs each folder's hooks, from inside that folder"
  (cd "$ws" && git init -q && git add -A && pre-commit run --all-files) || fail "workspace: pre-commit run --all-files"
  spacing="backend/$(dirname "$(cd "$ws/backend" && find src -name '*.csproj' | head -n 1)")/Spacing.cs"
  printf 'namespace Demo;\npublic static class Spacing\n{\n        public static int One()   =>   1;\n}\n' >"$ws/$spacing"
  printf 'export   const   spaced="b"\n' >"$ws/frontend/src/app/spaced.ts"
  out="$(cd "$ws" && git add -A && pre-commit run 2>&1)" && fail "workspace: badly formatted files passed pre-commit"
  grep -q 'Spacing.cs.*WHITESPACE' <<<"$out" || fail "workspace: backend/ dotnet format missed the staged file: $out"
  grep -qxF 'export const spaced = "b";' "$ws/frontend/src/app/spaced.ts" ||
    fail "workspace: frontend/ prettier missed the staged file: $out"
  (cd "$ws" && git reset -q && rm "$spacing" frontend/src/app/spaced.ts)

  log "workspace: the root's Claude hooks run each folder's own hooks"
  for found in .pre-commit-config.yaml backend/Directory.Build.props frontend/eslint.config.mjs; do
    settings_blocks "$ws" "$found" || fail "workspace: the root's settings.json lets an edit of $found through"
  done
  settings_blocks "$ws" frontend/src/app/app.ts && fail "workspace: the root's settings.json blocks a source file"
  bash "$work/src/scripts/test-hooks.sh" "$ws/backend" dotnet "$ws" || fail "workspace: backend hooks"
  bash "$work/src/scripts/test-hooks.sh" "$ws/frontend" angular "$ws" || fail "workspace: frontend hooks"
}

for stack in $stacks; do
  if [[ "$stack" == workspace ]]; then check_workspace; continue; fi
  # .NET is generated once per architecture; the other stacks have none ("-").
  # Clean Architecture is generated once per use-case style (architecture:use_cases).
  architectures="-"
  [[ "$stack" == dotnet ]] && architectures="simple clean:plain clean:handlers clean:mediator vertical-slice modular-monolith"
  for variant in $architectures; do
  architecture="${variant%%:*}"
  use_cases=""
  [[ "$variant" == *:* ]] && use_cases="${variant#*:}"
  for org in $orgs; do
    name="$stack-$org"
    arch_args=()
    if [[ "$architecture" != - ]]; then
      name="$stack-$architecture${use_cases:+-$use_cases}-$org"
      arch_args=(--data "architecture=$architecture")
      [[ -n "$use_cases" ]] && arch_args+=(--data "use_cases=$use_cases")
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
          fail "$name: VSA-2 or VSA-7 not enforced (a reference into a feature passed the architecture tests)"
      fi
      if [[ "$architecture" == modular-monolith ]]; then
        check_module_boundaries "$dir" "$(basename "$first_project" .csproj | sed 's/\.Host$//')" ||
          fail "$name: MOD-1 or MOD-2 not enforced (a public module type or a cross-module reference passed)"
      fi
      if [[ "$architecture" == clean ]]; then
        if [[ "$use_cases" == plain ]] && grep -q '^- \*\*CLEAN-14 ' "$dir/AGENTS.md"; then
          fail "$name: the CQRS rule CLEAN-14 is rendered for plain use cases"
        fi
        check_use_case_isolation "$dir" "$(basename "$first_project" .csproj | sed 's/\.[^.]*$//')" ||
          fail "$name: CLEAN-10 not enforced (a call between use cases passed, or a similar name failed)"
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
mkdir -p "$dup" && tar -C "$root" -cf - rules orgs config | tar -C "$dup" -xf -
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
mkdir -p "$cross" && tar -C "$root" -cf - rules orgs config | tar -C "$cross" -xf -
printf '
- **ME-1 [review]** Personal rule.
' >>"$cross/orgs/personal/rules.md"
printf '
- **ME-1 [review]** Corp rule.
' >>"$cross/orgs/example-corp/rules.md"
python3 "$work/src/scripts/check_rules.py" "$cross" >/dev/null || fail "check_rules: same ID in two orgs reported"

log "fresh project: CLAUDE.md imports AGENTS.md exactly once"
fresh="$(find "$work" -maxdepth 1 \( -name '*-personal' -o -name workspace \) | head -n 1)"
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
