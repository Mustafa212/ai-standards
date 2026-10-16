#!/usr/bin/env bash
# End-to-end fix-debt proof on a rendered project, through the script commands (not the AI):
# plant a too-many-parameters function with a test, audit, and pay the item with a correct fix
# (verdict DONE), then with a fix that drops a test and adds a suppression (verdict STOPPED).
# Usage: scripts/test-fix-debt.sh <standards src> <rendered project> <python|typescript> <work dir>
set -euo pipefail

src="$1" rendered="$2" stack="$3" work="$4"
project="$work/debt $stack" # a space, as real paths have
out="$work/debt-out-$stack"
failed=0
fail() { printf '\033[31mFAIL: fix-debt %s: %s\033[0m\n' "$stack" "$*"; failed=1; }
git_q() { git -c user.email=t@t -c user.name=t -c commit.gpgsign=false -c core.autocrlf=false "$@"; }
fd() { python3 "$src/scripts/fix_debt.py" "$@"; }
rm -rf "$project" "$out"
mkdir -p "$project"
tar -C "$rendered" --exclude=.git --exclude=.venv -cf - . | tar -C "$project" -xf -

case "$stack" in
  python)
    pkg_init="$(find "$project/src" -mindepth 2 -maxdepth 2 -name __init__.py | head -1)"
    pkg="$(basename "$(dirname "$pkg_init")")"
    code="src/$pkg/shipping.py"
    cat >"$project/$code" <<'PY'
"""Shipping costs."""


def shipping_cost(weight, distance, express, fragile, insured, weekend):
    """Cost of one parcel."""
    cost = weight * 2 + distance
    if express:
        cost += 10
    if fragile or insured or weekend:
        cost += 5
    return cost
PY
    cat >"$project/tests/test_shipping.py" <<PY
from $pkg.shipping import shipping_cost


def test_express_parcel_costs_more() -> None:
    assert shipping_cost(1, 10, True, False, False, False) == 22


def test_extras_add_five() -> None:
    assert shipping_cost(1, 10, False, True, False, False) == 17
PY
    command='uv run pytest --junitxml={result}'; format=junit
    fixed='"""Shipping costs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Parcel:
    """One parcel and its options."""

    weight: int
    distance: int
    express: bool = False
    extras: bool = False


def shipping_cost(parcel: Parcel) -> int:
    """Cost of one parcel."""
    cost = parcel.weight * 2 + parcel.distance
    if parcel.express:
        cost += 10
    if parcel.extras:
        cost += 5
    return cost
'
    fixed_test="from $pkg.shipping import Parcel, shipping_cost


def test_express_parcel_costs_more() -> None:
    assert shipping_cost(Parcel(1, 10, express=True)) == 22


def test_extras_add_five() -> None:
    assert shipping_cost(Parcel(1, 10, extras=True)) == 17
"
    test_file="tests/test_shipping.py"; canary_line=8; canary_text='        cost += 11'
    (cd "$project" && uv sync --quiet)
    ;;
  typescript)
    code="src/shipping.ts"
    cat >"$project/$code" <<'TS'
/** Cost of one parcel. */
export function shippingCost(weight: number, distance: number, express: boolean, fragile: boolean, insured: boolean): number {
  let cost = weight * 2 + distance;
  if (express) {
    cost += 10;
  }
  if (fragile || insured) {
    cost += 5;
  }
  return cost;
}
TS
    cat >"$project/src/shipping.test.ts" <<'TS'
import { describe, expect, it } from "vitest";
import { shippingCost } from "./shipping";

describe("shippingCost", () => {
  it("charges more for express", () => {
    expect(shippingCost(1, 10, true, false, false)).toBe(22);
  });
  it("adds five for extras", () => {
    expect(shippingCost(1, 10, false, true, false)).toBe(17);
  });
});
TS
    command='npx vitest run --reporter=default --reporter=junit --outputFile.junit={result}'; format=junit
    fixed='/** One parcel and its options. */
export interface Parcel {
  readonly weight: number;
  readonly distance: number;
  readonly express?: boolean;
  readonly extras?: boolean;
}

/** Cost of one parcel. */
export function shippingCost(parcel: Parcel): number {
  let cost = parcel.weight * 2 + parcel.distance;
  if (parcel.express === true) {
    cost += 10;
  }
  if (parcel.extras === true) {
    cost += 5;
  }
  return cost;
}
'
    fixed_test='import { describe, expect, it } from "vitest";
import { shippingCost } from "./shipping";

describe("shippingCost", () => {
  it("charges more for express", () => {
    expect(shippingCost({ weight: 1, distance: 10, express: true })).toBe(22);
  });
  it("adds five for extras", () => {
    expect(shippingCost({ weight: 1, distance: 10, extras: true })).toBe(17);
  });
});
'
    test_file="src/shipping.test.ts"; canary_line=5; canary_text='    cost += 11;'
    ;;
  *) echo "test-fix-debt.sh: stack $stack isn't covered" >&2; exit 2 ;;
esac

git_q -C "$project" init -q
git_q -C "$project" add -A
git_q -C "$project" commit -qm "a project with debt"

# Audit it: render the standards for this project, run the tools, write the report.
render="$work/debt-render-$stack"
rm -rf "$render"
cp -r "$rendered" "$render"
python3 "$src/scripts/audit.py" tools "$project" --stack "$stack" --org personal --render "$render" --out "$out" >/dev/null
python3 "$src/scripts/audit.py" report "$out" --project-name debt --org personal --stack "$stack" --sha x >/dev/null
fd items "$out" --org personal >/dev/null
item="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(next(i["id"] for i in d["items"] if i["rule"]=="RDB-1"))' "$out/fix-debt/items.json")" ||
  { fail "no RDB-1 item from the planted function"; exit 1; }

pay() { # <batch> <fixed code> <fixed test> <extra commit step>: run one item; print the verdict's exit code
  local batch="$out/fix-debt/$1" dir
  dir="$(fd start "$project" "$batch" --item "$item" --items "$out/fix-debt/items.json" --allow "$test_file")"
  fd test "$project" --command "$command" --format "$format" --out "$dir/clean.json" >/dev/null
  fd canary "$project" --file "$code" --line "$canary_line" --replace "$canary_text" --command "$command" \
    --format "$format" --clean "$dir/clean.json" --out "$dir/canary.json" >/dev/null
  printf '%s' "$2" >"$project/$code"
  printf '%s' "$3" >"$project/$test_file"
  $4
  git_q -C "$project" add -A
  git_q -C "$project" commit -qm "refactor: pay RDB-1 debt in src"
  fd test "$project" --command "$command" --format "$format" --out "$dir/after.json" >/dev/null
  fd verify "$project" --item-dir "$dir" --stack "$stack" --org personal --render "$render" \
    --before "$out/tool-findings.json" >/dev/null
  set +e; fd verdict "$project" --item-dir "$dir" >"$dir/verdict.out"; echo "$?"; set -e
}

base="$(git -C "$project" rev-parse HEAD)"
code_done="$(pay good "$fixed" "$fixed_test" true)"
[[ "$code_done" == 0 ]] || fail "a correct fix wasn't DONE: $(cat "$out/fix-debt/good/"*/verdict.out)"

git_q -C "$project" reset -q --hard "$base"
# shellcheck disable=SC2317  # bad_step runs through pay's fourth argument
bad_step() { # drop a test and silence a rule instead of fixing it
  sed -i '/adds five\|extras_add_five/,+2d' "$project/$test_file"
  if [[ "$stack" == python ]]; then echo "x = 1  # noqa: PLR2004" >>"$project/$code"; else echo "// eslint-disable-next-line" >>"$project/$code"; fi
}
code_bad="$(pay bad "$fixed" "$fixed_test" bad_step)"
[[ "$code_bad" == 1 ]] || fail "a fix that drops a test and adds a suppression wasn't STOPPED"
verdict_bad="$(cat "$out/fix-debt/bad/"*/verdict.out)"
grep -q "nothing lost.*FAIL" <<<"$verdict_bad" || fail "the dropped test wasn't reported"
grep -q "suppression added" <<<"$verdict_bad" || fail "the suppression wasn't reported"

exit "$failed"
