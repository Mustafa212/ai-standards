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

lint_rule_ids() { # <stack> <project dir> <file> -> one fired rule id per line
  local stack="$1" dir="$2" file="$3"
  if [[ "$stack" == typescript ]]; then
    (cd "$dir" && npx --no-install eslint --format json "$file" || true) |
      jq -r '.[].messages[].ruleId // empty'
  else
    (cd "$dir" && $RUN ruff check --output-format json "$file" || true) | jq -r '.[].code // empty'
  fi
}

check_violations() { # <stack> <org> <project dir> <dest folder for violation files>
  local stack="$1" org="$2" dir="$3" dest="$4" file expected fired rule
  local -a files=()
  shopt -s nullglob
  files+=("$work/src/tests/violations/$stack"/*.{ts,py})
  files+=("$work/src/tests/violations/$stack/$org"/*.{ts,py})
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

for stack in $stacks; do
  for org in $orgs; do
    name="$stack-$org"
    dir="$work/$name"
    log "$name: generate"
    copier_cmd copy --trust --defaults --quiet \
      --data project_name="Test $stack $org" --data org="$org" --data stack="$stack" \
      --data 'ai_tools=["claude","cursor","copilot"]' \
      "$work/src" "$dir"

    # shellcheck disable=SC2016  # literal ${{ is GitHub Actions syntax, allowed in workflows
    if leftovers="$(grep -rn --exclude-dir=node_modules -e '{%' -e '{{' "$dir" | grep -v '\${{')"; then
      fail "$name: unrendered template syntax"; echo "$leftovers"
    fi

    log "$name: install + check"
    if [[ "$stack" == typescript ]]; then
      (cd "$dir" && npm install --no-audit --no-fund --silent)
      (cd "$dir" && npm run --silent check) || fail "$name: npm run check"
      check_violations "$stack" "$org" "$dir" "$dir/src"
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
      [[ -z "$RUN" ]] && deactivate
    fi
  done
done

if ((${#failures[@]})); then
  log "${#failures[@]} failure(s)"; printf ' - %s\n' "${failures[@]}"; exit 1
fi
log "all templates OK"
