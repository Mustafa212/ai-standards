---
name: adopt-project
description: Use when the user wants the ai-standards tools added to an EXISTING typescript or python repository (full adoption), usually after onboard registered it. Adds the standard configs without overwriting anything, baselines old lint findings so CI enforces new code from day one, and writes a prioritized debt plan (docs/STANDARDS-DEBT.md). Writes to the repository and offers commits. For a read-only check or report of how far a project is from its rules, use the audit skill instead.
---

# Adopt an existing project

Goal: from day one, every **new or changed** line meets the standards, while the existing code
keeps working and its debt is paid down deliberately, item by item. Nothing the user wrote is
overwritten or deleted, and nothing is committed without their OK.

Template source (`<source>` below): the `Source:` line of `~/.claude/ai-standards/config.md`
(the user's private copy, set up by the `onboard` skill) if that file exists, else
`${user_config.standards_source}`. Default org: `${user_config.default_org}`.
Usually the `onboard` skill runs this one, after it has asked the org and registered the project.

Work in four gated steps. Stop at each gate for the user's answer.

## 1. Audit (read-only)

1. `git status`: the tree must be clean so every change is reviewable. If it isn't, ask the user to
   commit or stash first.
2. Detect the stack. An `angular.json` → `angular`, a `.sln`/`.slnx`/`.csproj` → `dotnet`, a
   `pubspec.yaml` → `flutter`: these three can't be adopted yet. Say so, say that the rules and
   `/ai-standards:audit` already work for them (through `/ai-standards:onboard`), and stop.
   Otherwise `package.json` + `.ts` files → `typescript`; `pyproject.toml` / `requirements*.txt` +
   `.py` → `python`. Anything else (monorepos with several stacks included) isn't supported yet: say
   so, offer `propose-rule` to add the stack, and stop. For typescript and python, read the stack's
   section of `references/stacks.md`: what the standard configs assume, and what can stop adoption
   here.
3. Read what the project already has: existing lint/format/type/test configs, CI workflows,
   `CLAUDE.md`/`AGENTS.md`/`CODING_RULES.md`, test command and whether tests pass today.
4. Measure, with the project's own tools: do the tests pass? current coverage %? does the type
   checker pass, and how many errors?

**Gate 1:** report in a few lines: stack, what exists, tests (pass/fail), coverage %, type errors,
and the proposed plan below. Ask which org. If the existing tests fail, stop: adoption must start
from a green baseline, so they get fixed (or explicitly skipped by the user) first.

## 2. Plan the adoption

Propose, with a recommendation for each:

- **Type checking**: enforce now if it passes today, otherwise `deferred` (runs in CI as a warning).
- **Coverage**: if measured ≥ the org target, enforce the target. If measured is between 1% and the
  target, enforce today's value as `coverage_floor` (ratchet). If there are no tests, `deferred`.
- **Config conflicts**: the project's own lint/tsconfig/etc. are kept; the standard versions arrive
  as `<file>.ai-standards` for a decision (step 3).
- **Commits**: three separate commits, so `git blame` stays useful: adopt files → format-only →
  lint baseline.

**Gate 2:** wait for approval.

## 3. Apply

Commands use `python3` and `uvx copier`; when one isn't available, and for the tools Python projects
need, see `${CLAUDE_PLUGIN_ROOT}/references/runners.md`.

1. Clone the standards repo to a temp dir for its scripts:
   `git clone --depth 1 https://github.com/<owner>/<repo> <tmp>/standards`.
2. Render the template into an empty temp dir, with the answers from step 2:
   ```bash
   uvx copier copy --trust --defaults \
     --data org=<org> --data stack=<stack> --data project_name="<name>" \
     --data adopted=true --data coverage_floor=<n or 0> --data 'deferred_checks=[<...>]' \
     --data 'ai_tools=["claude"]' --data standards_source="<source>" \
     "<source>" <tmp>/rendered
   ```
   Use the remote source so later `copier update` runs work.
3. Merge without overwriting: `python3 <tmp>/standards/scripts/adopt.py <tmp>/rendered .`
   Never `copier copy` into the project, never `--overwrite`.
4. Walk the user through the report: every "Kept yours, differs", "Not added" (for example
   `"type": "module"`, which would break CommonJS) and `*.ai-standards` file. Usual answer for lint
   and type configs: take the standard one (the baseline below absorbs the fallout); for build
   scripts and runtime settings: keep theirs. Delete each `*.ai-standards` once decided.
5. Install: `npm install` or `uv sync`. Then `pre-commit install --install-hooks -t pre-commit -t commit-msg`.
   Python projects that kept their own `pyproject.toml` need the standard dev tools in it:
   `uv add --dev mypy pre-commit pytest pytest-cov ruff` (`make check` names any that are missing).
6. Offer commit 1: `chore: adopt ai-standards`.
7. **Format-only commit:** `npm run format` or `uv run ruff format .`. Offer commit 2
   `style: apply standard formatting`, then add its SHA to `.git-blame-ignore-revs` (create it) and
   run `git config blame.ignoreRevsFile .git-blame-ignore-revs`.
8. **Lint baseline** (old violations recorded, new ones still fail):
   - TypeScript: `npx eslint . --suppress-all` (writes `eslint-suppressions.json`).
   - Python: `uv run ruff check . --add-noqa`, then `uv run ruff format .`; repeat both until
     `uv run ruff check .` is clean (at most 3 times; lines can get long).
   Offer commit 3: `chore: baseline existing lint findings`.
9. Run the full check (`npm run check` / `make check`). It must pass now. If it doesn't, the cause is
   usually a test failure or a step skipped above; fix that, never a managed config.

## 4. Debt plan and report

1. Write the plan: `python3 <tmp>/standards/scripts/standards_audit.py .` → `docs/STANDARDS-DEBT.md`.
   Offer to commit it with the baseline or on its own (`docs: add standards debt plan`).
2. Tell the user, briefly:
   - what is enforced from now on (all rules on new and changed lines; type checking and coverage
     as decided),
   - the debt: totals per priority (P1 correctness and security first), and the top 3 items,
   - how it gets paid: `/ai-standards:fix-debt` takes the next item, one per commit, and ratchets
     the standards up as areas get clean,
   - that `CLAUDE.md` stays theirs, and that monthly update PRs keep the standards current.
