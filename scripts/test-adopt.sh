#!/usr/bin/env bash
# End-to-end test of adopting an existing, messy project — the adopt-project skill's steps, scripted.
# Usage: scripts/test-adopt.sh <standards source dir> <work dir> <typescript|python>
#
# Proves: nothing of the user's is lost; after format + baseline the full check passes; a NEW
# violation still fails; fixing old debt forces a baseline prune (ratchet); the audit writes a
# prioritized plan; and `copier update --data ...` ratchets the settings up.
set -uo pipefail

src="$1"
work="$2"
stack="$3"
project="$work/legacy-$stack"
failures=0
fail() { printf '\033[31mFAIL: adopt/%s: %s\033[0m\n' "$stack" "$*"; failures=$((failures + 1)); }
step() { printf '\n\033[1m-- adopt/%s: %s\033[0m\n' "$stack" "$*"; }
git_q() { git -c user.email=t@t -c user.name=t -c commit.gpgsign=false "$@"; }
commit() { (cd "$project" && git_q add -A && git_q commit -qm "$1" --no-verify); }

copier_cmd() {
  if command -v copier >/dev/null 2>&1; then copier "$@"
  elif command -v uvx >/dev/null 2>&1; then uvx copier "$@"
  else pipx run copier "$@"; fi
}

# Copier renders from a git repo (as it would from GitHub), so updates can be tested.
template="$work/template-git"
rm -rf "$template" && mkdir -p "$template"
tar -C "$src" --exclude=.git --exclude=node_modules -cf - . | tar -C "$template" -xf -
(cd "$template" && git init -q && git_q add -A && git_q commit -qm base && git tag v9.0.0)

step "create a legacy project"
rm -rf "$project" && mkdir -p "$project/src"
if [[ "$stack" == typescript ]]; then
  cat >"$project/package.json" <<'EOF'
{ "name": "legacy", "private": true, "type": "module",
  "scripts": { "test": "vitest run" }, "dependencies": { "zod": "^3.23.0" } }
EOF
  printf '{ "compilerOptions": { "strict": false, "target": "ES2022", "module": "NodeNext", "moduleResolution": "NodeNext", "noEmit": true }, "include": ["src"] }\n' >"$project/tsconfig.json"
  cat >"$project/src/pricing.ts" <<'EOF'
export function price(base: any, qty: number) {
    if (qty == 0) return 0
    return base * qty * 1.15
}
export function label(n) { return "item-" + n }
EOF
  cat >"$project/src/pricing.test.ts" <<'EOF'
import { describe, expect, it } from "vitest";
import { price } from "./pricing.js";
describe("price", () => { it("adds tax", () => { expect(price(10, 2)).toBeCloseTo(23); }); });
EOF
else
  printf '[project]\nname = "legacy"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n' >"$project/pyproject.toml"
  mkdir -p "$project/src/legacy" "$project/tests"
  : >"$project/src/legacy/__init__.py"
  cat >"$project/src/legacy/pricing.py" <<'EOF'
import os
def price(base, qty):
    if qty == 0:
        return 0
    try:
        return base * qty * 1.15
    except:
        pass
def data_path(name):
    return os.path.join("data", name)
EOF
  cat >"$project/tests/test_pricing.py" <<'EOF'
import pytest
from legacy.pricing import price
def test_adds_tax():
    assert price(10, 2) == pytest.approx(23)
EOF
fi
printf 'Team notes: use the staging DB for manual tests.\n' >"$project/CLAUDE.md"
(cd "$project" && git init -q && git_q add -A && git_q commit -qm "legacy" --no-verify)
cp "$project/CLAUDE.md" "$work/claude-before.md"

step "render + merge (adopted, typecheck deferred, coverage floor 40)"
copier_cmd copy --trust --defaults --quiet \
  --data org=personal --data stack="$stack" --data project_name=legacy \
  --data adopted=true --data coverage_floor=40 --data 'deferred_checks=["typecheck"]' \
  "$template" "$work/rendered-$stack" >/dev/null
python3 "$src/scripts/adopt.py" "$work/rendered-$stack" "$project" >"$work/adopt-report-$stack.txt"
grep -q 'Team notes' "$project/CLAUDE.md" || fail "user's CLAUDE.md content lost"
[[ "$(head -n 1 "$project/CLAUDE.md")" == "@AGENTS.md" ]] || fail "CLAUDE.md lacks the AGENTS.md import"
grep -q '## Adoption status' "$project/AGENTS.md" || fail "AGENTS.md has no Adoption status section"
# The user's decisions in the walkthrough: take the standard tool configs, keep their own
# pyproject.toml (it holds their dependencies), as the adopt-project skill recommends.
rm -f "$project/pyproject.toml.ai-standards"
for review in $(cd "$project" && find . -name '*.ai-standards' -not -path './node_modules/*'); do
  mv "$project/$review" "$project/${review%.ai-standards}"
done
if [[ "$stack" == typescript ]]; then
  jq -e '.dependencies.zod' "$project/package.json" >/dev/null || fail "user's dependency lost"
fi
commit "chore: adopt ai-standards"

step "install, format-only commit, lint baseline"
if [[ "$stack" == typescript ]]; then
  (cd "$project" && npm install --no-audit --no-fund --silent >/dev/null 2>&1) || fail "npm install"
  (cd "$project" && npm run --silent format >/dev/null)
  commit "style: apply standard formatting"
  (cd "$project" && npx eslint . --suppress-all >/dev/null 2>&1)
  [[ -f "$project/eslint-suppressions.json" ]] || fail "no eslint-suppressions.json"
  check=(npm run --silent check)
  lint=(npx eslint .)
else
  # Their pyproject.toml lacks the standard dev tools: check must say so and name the fix.
  (cd "$project" && make deps 2>&1 | grep -q 'uv add --dev mypy pytest pytest-cov ruff') ||
    fail "missing dev dependencies not reported by make deps"
  (cd "$project" && uv add --quiet --dev mypy pre-commit pytest pytest-cov ruff) || fail "uv add --dev"
  (cd "$project" && uv sync --quiet 2>/dev/null) || fail "uv sync"
  (cd "$project" && uv run --quiet ruff format . >/dev/null 2>&1)
  commit "style: apply standard formatting"
  for _ in 1 2 3; do
    (cd "$project" && uv run --quiet ruff check . --add-noqa >/dev/null 2>&1 && uv run --quiet ruff format . >/dev/null 2>&1)
    (cd "$project" && uv run --quiet ruff check . >/dev/null 2>&1) && break
  done
  check=(make check)
  lint=(uv run --quiet ruff check .)
fi
(cd "$project" && "${check[@]}" >"$work/check-$stack.log" 2>&1) || { fail "full check fails after baseline"; tail -25 "$work/check-$stack.log"; }
commit "chore: baseline existing lint findings"

step "audit writes the debt plan"
(cd "$project" && python3 "$src/scripts/standards_audit.py" . >/dev/null) || fail "audit failed"
plan="$project/docs/STANDARDS-DEBT.md"
grep -qE "\*\*[1-9][0-9]* baselined finding" "$plan" || fail "plan has no findings count"
grep -q '### P1. Correctness and security' "$plan" || fail "plan has no P1 section"
grep -q 'typecheck' "$plan" || fail "deferred typecheck missing from plan"
grep -q 'Enable type checking' "$plan" || fail "ratchet section missing"
commit "docs: add standards debt plan"

step "a NEW violation still fails (baseline doesn't cover new code)"
if [[ "$stack" == typescript ]]; then
  printf 'export const fee = Number(42);\n' >>"$project/src/pricing.ts"
else
  printf 'print(42)\n' >>"$project/src/legacy/pricing.py"
fi
(cd "$project" && "${lint[@]}" >/dev/null 2>&1) && fail "new violation passed lint"
(cd "$project" && git checkout -q -- .)

step "fixing old debt forces a baseline prune (ratchet)"
if [[ "$stack" == typescript ]]; then
  sed -i 's/qty == 0/qty === 0/' "$project/src/pricing.ts"
  (cd "$project" && npx eslint . >/dev/null 2>&1) && fail "stale suppression was not reported"
  (cd "$project" && npx eslint . --prune-suppressions >/dev/null 2>&1)
else
  # Pay the bare-except debt (E722 and, with a specific exception, S110 too).
  sed -i 's/except:  # noqa: \([A-Z0-9, ]*\)/except TypeError:  # noqa: \1/' "$project/src/legacy/pricing.py"
  (cd "$project" && uv run --quiet ruff check . >/dev/null 2>&1) && fail "stale noqa was not reported"
  (cd "$project" && uv run --quiet ruff check . --fix >/dev/null 2>&1)
fi
(cd "$project" && "${lint[@]}" >/dev/null 2>&1) || fail "lint still fails after pruning"
if [[ "$stack" == python ]]; then
  grep -qx '    except TypeError:' "$project/src/legacy/pricing.py" ||
    fail "stale noqa for the paid debt not pruned: $(grep -n 'except' "$project/src/legacy/pricing.py")"
  grep -q 'def price(base, qty):  # noqa: ANN001, ANN201' "$project/src/legacy/pricing.py" ||
    fail "prune removed live baseline entries: $(grep -n 'def ' "$project/src/legacy/pricing.py")"
fi
commit "refactor: pay debt"

step "copier update ratchets settings (floor 40 -> 60, enable typecheck)"
(cd "$project" && copier_cmd update --trust --defaults --conflict rej \
  --data coverage_floor=60 --data 'deferred_checks=[]' >"$work/update-$stack.log" 2>&1) ||
  { fail "copier update failed"; tail -5 "$work/update-$stack.log"; }
rejects="$(cd "$project" && find . -name '*.rej' -not -path './node_modules/*')"
[[ -z "$rejects" ]] || fail "update left conflicts: $rejects"
if [[ "$stack" == typescript ]]; then
  grep -q 'coverageThreshold = 60' "$project/vitest.config.ts" || fail "coverage floor not raised"
  sed -n '/^  check: \[/,/^  \],/p' "$project/.ai-standards/run.mjs" | grep -q '"tsc"' || fail "typecheck not re-enabled"
  jq -e '.dependencies.zod' "$project/package.json" >/dev/null || fail "user's dependency lost on update"
  jq -e '.scripts.test == "vitest run"' "$project/package.json" >/dev/null || fail "user's test script lost on update"
else
  grep -q 'cov-fail-under=60' "$project/pytest.ini" || fail "coverage floor not raised"
  grep -qE '^check: .*typecheck' "$project/Makefile" || fail "typecheck not re-enabled"
fi
grep -q 'Type checking: enforced' "$project/AGENTS.md" || fail "AGENTS.md adoption status not updated"
grep -q 'Team notes' "$project/CLAUDE.md" || fail "CLAUDE.md content lost on update"

exit $((failures > 0))
