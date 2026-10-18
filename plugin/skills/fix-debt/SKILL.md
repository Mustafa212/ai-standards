---
name: fix-debt
description: Use when the user wants to pay down standards debt in a project registered with or adopted onto ai-standards ("fix the debt", "pay the debt", "clean up the lint baseline", "next items in the report"), on any stack. Changes code after one approval: one commit per item and one pull request per round.
---

# Pay down standards debt, in rounds with computed proof

Debt work is its own change, never mixed into a feature (ADOPT-2). **A script decides whether an
item is done** (`fix_debt.py verdict`); your account of it is never evidence.

Paths:
- `<clone>`: the private copy in `~/.claude/ai-standards/config.md` that registers this project (with several `Clone:` lines, the one whose `orgs/*/projects/*.md` has its repo).
- `<out>`: `~/.claude/ai-standards/reports/<org>/<slug>/`, found as in the audit skill's step 1.
- `fd`: `python3 <clone>/scripts/fix_debt.py` (another Python: `${CLAUDE_PLUGIN_ROOT}/references/runners.md`). A private copy without `scripts/fix_debt.py` predates 0.11.0: offer `git -C <clone> pull upstream main --tags` (ask first).
- Evidence: `<out>/fix-debt/<batch>/<item>/`, where `<batch>` is `<date>-<n>`. It never goes in the project.
- `fd` exit codes: 0 done, 1 STOPPED (verdict), 2 the script failed (stop the round and report it; never reset), 3 several dotnet solutions (verify).

## 1. The round

1. **Source:**
   - **Registered, not adopted:** `<out>/findings.json`. If its `sha` isn't `git rev-parse --short HEAD`, run the `ai-standards:audit` skill first.
   - **Adopted** (the project has an "Adoption status" in `AGENTS.md`, typescript or python): `fd baseline <project> --stack <stack> --out <out>/fix-debt/baseline.json`.
2. **Items:** `fd items <out> --org <org> --project <project>` (adopted: add `--baseline <out>/fix-debt/baseline.json --stack <stack>`). This writes `<out>/fix-debt/items.json`: up to 10 behavior-preserving items in priority order, plus the P1 items apart. Within a priority, the folders with the most commits in the last 90 days come first: debt there is copied into every new change.
3. **The test command,** once per project, saved in `<out>/fix-debt/command.md`. Use `{result}` (the result file) or `{dir}` (its folder, new for each run) where the runner writes:

   | Runner | Command | `--format` |
   |---|---|---|
   | dotnet | `dotnet test <sln> --logger trx --results-directory {dir}` | `trx` |
   | dotnet on Microsoft.Testing.Platform (`global.json` has `"test": {"runner": "Microsoft.Testing.Platform"}`) | `cd <folder with global.json> && dotnet test --solution <sln> --report-xunit-trx --results-directory {dir}` (xunit.v3), or `--report-trx` with `Microsoft.Testing.Extensions.TrxReport`. From any other folder `dotnet test` falls back to VSTest and rejects `--solution` | `trx` |
   | pytest | `<python> -m pytest --junitxml={result}` | `junit` |
   | vitest | `npx vitest run --reporter=default --reporter=junit --outputFile.junit={result}` | `junit` |
   | jest | `npx jest --json --outputFile={result}` | `jest` |
   | flutter | `flutter test --reporter json > {result}` | `flutter` |
   | Karma, unittest, other | the project's own test command | `summary` (weaker: counts only) |

   Never add a package or reporter to the project for this. A run that takes minutes: run each
   `fd test` and `fd canary` in the background and wait for it, never starting another `fd` meanwhile.
   `--timeout <seconds>` (default 3600) turns a hung run into a run with no result.
4. **Ask once** (one message, then wait):
   - the items table (rule with its short text, folder, count, priority, kind, commits in 90 days);
   - the P1 items apart, each with the behavior it changes. The user picks them by number, one by one;
   - an item whose fix would change a response, a status code or stored data (a P2 such as 422 → 409)
     goes with the P1 items, whatever its priority: it changes behavior too;
   - the branch (`refactor/standards-debt-<date>`, or the open debt branch and its PR);
   - the test command and how long its last run took;
   - "At the end: push `<branch>` to `<remote>` and open a PR to `<base>` on <host>."

   That yes covers exactly this; nothing else is pushed or opened.

## 2. Each item, back to back

On the batch branch, with a clean working tree:

1. `fd start <project> <out>/fix-debt/<batch> --item <id> --items <out>/fix-debt/items.json [--allow <path>]... [--formatter-only]`. It prints the item folder `<dir>`.
   - `--allow` a file outside the item's folder that the fix must change: a shared file, the P1 test, or an analyzer setting the user approved.
   - Pass `--formatter-only` only when the stack's formatter or a tool's safe autofix settles the item: `dotnet format`, `ruff check --fix` (safe fixes), `eslint --fix`, `dart fix --apply`. Such an item skips steps 3 and 4.
2. `fd test <project> --command "<cmd>" --format <f> --out <dir>/clean.json`. Stop the round when:
   - tests fail in this clean run: say which ones fail on the base;
   - it has no result or 0 tests executed: show the error and ask for the right command.
3. **Canary:** pick one line the fix will touch whose change would alter behavior (a comparison, a constant, a branch), in a file the fix changes, and break it in a way that compiles: `fd canary <project> --file <f> --line <n> --replace "<text>" --command "<cmd>" --format <f> --clean <dir>/clean.json --out <dir>/canary.json`.
   - `--replace` is the whole new line, indentation included.
   - Vanished tests mean the break hid them (it didn't compile): pick another break.
   - Then `git status` must be clean. If it isn't, run `git checkout -- <f>` and stop the round.
4. **No new failures** means no test sees this code, so pin it first:
   1. Write characterization tests with literal inputs and outputs, asserting what the code does today, odd results included. Use the project's test conventions and folders, and the expected values worked out by hand.
   2. Commit them alone, as `test: pin <area> before <rule>`.
   3. Right after that commit, run `fd test … --out <dir>/pinned.json`. They must pass.
   4. Run the canary again; it must now fail at least one of them.
5. **P1 item:** first write the test of the intended behavior, run `fd test … --out <dir>/red.json` and see it fail. It goes in the fix commit.
6. **Fix:**
   - No suppressions, `noqa`, `eslint-disable`, `@ts-ignore`, `// ignore:`, baseline entries or severity changes (ADOPT-3).
   - No changes to analyzer or lint settings (ruff or mypy config, `pyproject.toml`, `.editorconfig`, eslint config, `tsconfig`, `*.csproj`, `Directory.Build.*`, `analysis_options.yaml`) unless the user approved them with `--allow`.
   - A genuine false positive is skipped with a written reason, never suppressed:
     `fd skip <out> --item <id> --reason "<why>"` keeps it out of later rounds until its count grows.
   - Commit `refactor: pay <rule> debt in <area>` (`fix:` for a P1).
   - Adopted projects: shrink the baseline in the same commit (typescript `npx eslint . --prune-suppressions`, python `uv run ruff check . --fix`).
7. `fd test … --out <dir>/after.json`
8. **Gone:**
   - **Tool item:** `fd verify <project> --item-dir <dir> --stack <s> --org <o> --render <tmp>/rendered --before <out>/tool-findings.json [--solution <sln>]`. Exit 3: several solutions; ask which and run again with `--solution`. Render as the audit skill's step 2 does, once per round.
   - **Review item:** dispatch one `ai-standards:rule-auditor` with the rule and the item's files only. Save its JSON and run `fd verify-review <project> --item-dir <dir> --review <json>`.
   - **Adopted item:** `fd verify-adopted <project> --item-dir <dir> --stack <s> --before <out>/fix-debt/baseline.json --check "<npm run check | make check>"`.
9. `fd verdict <project> --item-dir <dir>`. Exit 0 means DONE, exit 1 STOPPED, exit 2 an error (stop the round and report it).
10. **Blind review**, when the senior-dev plugin (1.6.0 or later) is installed:
    1. Write `git diff <start>..HEAD > <dir>/change.diff`, then dispatch `senior-dev:reviewer` with `references/reviewer-brief.md` filled in.
    2. CHANGES_REQUIRED: one fix round (steps 6–9 again), then a second review.
    3. Still required: the item is STOPPED.

    Without senior-dev, say the items weren't independently reviewed.
11. Append `<id> — <DONE|STOPPED> — <HEAD short sha>` to `<batch>/batch.md`. **DONE:** next item. **STOPPED** (exit 1 only):
    1. Show `verdict.md`.
    2. `git reset --hard <start>` (the `start` in `<dir>/item.json`). This removes only this item's own commits on the batch branch.
    3. End the round.

## 3. End of the round

1. **Push the branch and open the PR, as approved:**
   - **GitHub:** `gh pr create`.
   - **Azure Repos:** the org's MCP server `repo_pull_request_write`, action `create`.

   The PR body holds:
   - one row per item: rule, folder, findings before → after, verdict;
   - each stopped item's reasons word for word;
   - each item's "Does not prove" lines;
   - whether a blind review ran.

   Nothing merges.
2. **Record:** `fd done <out> --item <id>` with one `--item` per DONE item, so the next round skips them.
3. **Report:** the items done and stopped, the tests executed before → after, and the PR link. Offer the next round.
4. **Adopted projects:** check the ratchet in the same report:
   - type errors at 0 → remove `typecheck` from `deferred_checks`;
   - coverage above `coverage_floor` → raise it.

   Apply with `uvx copier update --trust --defaults --data …`, never by editing managed files.

Stopped mid-round: `batch.md` in the batch folder lists each item's state, and the next fix-debt resumes from it.
