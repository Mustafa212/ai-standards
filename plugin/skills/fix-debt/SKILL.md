---
name: fix-debt
description: Use when the user wants to pay down standards debt in a project adopted onto ai-standards ("fix the debt", "clean up the lint baseline", "raise coverage", "enable type checking", "next item in STANDARDS-DEBT.md"). Takes the highest-priority item from docs/STANDARDS-DEBT.md, fixes it in its own change, shrinks the baseline and ratchets the standards up.
---

# Pay down standards debt, one item at a time

Works in projects whose `AGENTS.md` has an "Adoption status" section. If there's no
`docs/STANDARDS-DEBT.md`, generate it first (step 1). Debt work is always its own change, never mixed
into a feature or bug fix (ADOPT-2).

## 1. Pick the item

1. Make sure the tree is clean and you're on a branch for this work (propose
   `refactor/standards-debt-<rule>` if on the default branch).
2. Refresh the plan so it reflects the code, not an old snapshot: clone the standards repo to a temp
   dir and run `python3 <tmp>/standards/scripts/standards_audit.py .` (`python` where `python3` is
   the Windows Store alias)
3. Take the first unchecked item in priority order (P1 → P4), unless the user named one. A large item
   is split by area: one directory or module per change, small enough to review in one sitting.

Tell the user in two lines what you'll fix and roughly how many places, then go ahead unless the
change touches behavior (P1 items often do): for those, show the plan and wait for OK.

## 2. Fix

- See the hidden (baselined) findings with the item's "see them" command. For TypeScript, create the
  empty baseline it needs first: `mkdir -p .ai-session && echo {} > .ai-session/no-baseline.json`.
- Fix the code. **Behavior must not change** unless the item is a real bug (P1); then add a test that
  fails without the fix, and say so in the commit.
- Never add suppressions, `noqa`, `eslint-disable` or baseline entries to make it pass (ADOPT-3).
  If a finding is a genuine false positive, use a specific suppression with a written reason (SUP-1)
  and list it in your report.
- Run the related tests after each file or small batch.

## 3. Shrink the baseline

- TypeScript: `npx eslint . --prune-suppressions`
- Python: `uv run ruff check . --fix` (RUF100 removes `noqa` codes that no longer suppress anything; never add `--select`, which makes every other code look unused)

Both CI linters fail on stale baseline entries, so this step can't be skipped.

## 4. Ratchet

Check whether this change unlocks a stricter setting, and if so propose it in the same report:

- Type errors reached 0 → remove `typecheck` from `deferred_checks`.
- Tests were added → measure coverage; if higher than `coverage_floor`, raise it to the new value
  (rounded down). Once it reaches the org target the floor no longer matters.

Apply with `copier update`, never by editing managed files:

```bash
uvx copier update --trust --defaults --data coverage_floor=<n> --data 'deferred_checks=[...]'
```

## 5. Verify and hand over

1. Full check (`npm run check` / `make check`) passes.
2. Regenerate `docs/STANDARDS-DEBT.md` with the audit script.
3. Report: item fixed, findings before → after, files touched, any behavior change and its test,
   any ratchet applied. Offer the commit: `refactor: pay <rule> debt in <area>` (or `fix:` for a real
   bug). Don't commit or push without the user's OK.
4. Offer the next item.
