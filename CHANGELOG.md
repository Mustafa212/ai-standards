# Changelog

Versions follow semver, from the point of view of a project that runs `copier update`:

- **MAJOR**: existing, previously-passing code may now fail checks (stricter threshold, new
  `[tool]` rule that errors). Projects should plan time for the update.
- **MINOR**: new `[review]`/`[ai]` rules, new orgs, stacks or tooling that does not fail existing code.
- **PATCH**: wording, docs, bug fixes in templates.

Each entry names the rule ID, the layer (base / stack / org) and the enforcement level.

## Unreleased

## 0.3.1

Fixes (no rule changes):

- **Monthly update PRs:** `create-pull-request` uses the `AI_STANDARDS_TOKEN` secret when set. With the
  default `GITHUB_TOKEN`, GitHub refused updates that touched `.github/workflows/` and never ran CI
  on the PR; the workflow now warns when the secret is missing.
- **Line endings:** `.gitattributes` (`* text=auto eol=lf`) in this repo and in generated projects
  (project-owned, line-merged on adopt). On Windows with `core.autocrlf=true`, clones got CRLF and
  `prettier --check` failed on every file.
- **Python hooks fail closed:** without `uv` they block the edit and say how to install it, instead of
  failing to start (which Claude Code treats as non-blocking, so managed files were unprotected).
  The managed-files hook runs with `--no-project`. The edit hook no longer skips files whose names
  start with `dist` (e.g. `distance.py`), and says how to install ruff when it's missing.
- **Python dev tools:** `make check` first checks that mypy, pytest, pytest-cov and ruff are installed
  and prints the `uv add --dev ...` command (adopted projects keep their own `pyproject.toml`).
  `pytest.ini` sets `pythonpath = src`, so projects that aren't installed as a package still import.
  pre-commit runs the project's own ruff instead of a separately pinned copy, so pre-commit, the edit
  hook and CI agree.
- **TypeScript:** `eslint.config.js` → `eslint.config.mjs`, so it loads in CommonJS projects too (adopt
  never adds `"type": "module"`). `copier update` removes the old file.
- **Plugin:** the adoption offer isn't repeated after a compaction. `adopt-project` checks the test runner
  (Vitest only; Jest suites are migrated first), module system and Python layout, installs the
  standard Python dev tools into a kept `pyproject.toml`, and works where `python3` is the Windows
  Store alias.
- **This repo:** CI calls `bash scripts/test-templates.sh` (immune to lost executable bits), and tag
  pushes now trigger the release job. The adopt e2e test keeps the legacy `pyproject.toml`, as users
  do, instead of replacing it.
- `AGENTS.md`: managed files must not be changed through shell commands either. README: prerequisites,
  the update token, and CODEOWNERS as the hard guard.

## 0.3.0

Existing projects:

- New `adopt-project` skill: read-only audit → approved plan → safe merge → format-only commit →
  lint baseline (`eslint-suppressions.json` / `ruff --add-noqa`) → debt plan. CI enforces new code
  from day one.
- New `fix-debt` skill and `scripts/standards_audit.py`, which writes `docs/STANDARDS-DEBT.md`: the
  baselined debt ordered P1 (correctness, security) → P4 (style), with commands to see each item.
- New answers `adopted`, `deferred_checks` (typecheck, coverage) and `coverage_floor` (ratchet).
  Deferred checks run in CI as non-blocking warnings. `AGENTS.md` gets an "Adoption status"
  section and rules ADOPT-1..3 (new lines clean; debt never mixed into feature work; baseline only
  shrinks).
- SessionStart offers adoption once in unadopted projects (opt out with `.ai-standards-skip`), and
  reports the debt summary in adopted ones.

Fixes:

- **`package.json` and `pyproject.toml` are now project-owned** (`_skip_if_exists`). Before,
  `copier update` could replace them with the template's version and move the project's own
  dependencies into a `.rej` file. Standard scripts delegate to the managed
  `.ai-standards/run.mjs`, which checks required dev dependencies and prints the install command.
- **Edit hook respects untouched code:** tracked files get lint errors reported only on lines
  changed since HEAD, no auto-fix, and formatting only if the file was already formatted.
  New files are formatted, fixed and linted in full.
- **Hooks work on Windows:** rewritten in Node (TypeScript stack) and Python (Python stack); the old
  bash hooks needed `jq`, which Git Bash lacks, and silently did nothing without it.
- `.ai-session/` (local AI working state) is git-ignored and skipped by ESLint, Prettier, Ruff and
  the hooks.
- `init-project` offers the commit instead of committing.

Rules:

- **PY-5 [tool]** (stack: python) `open()` needs an explicit encoding (Ruff `PLW1514`); no mutable
  default arguments (`B006`). **BREAKING** for Python code that opens files without an encoding.

## 0.2.0

- `CLAUDE.md` is now project-owned: created once, never overwritten (`_skip_if_exists`), no longer
  blocked by the managed-files hook. A Copier task guarantees only the `@AGENTS.md` import line.
- Claude Code instructions moved from `CLAUDE.md` into an "## Claude Code" section of `AGENTS.md`.
- New `scripts/adopt.py`: safe merge into existing projects (never overwrites; JSON key merge,
  `.gitignore` line merge, `<file>.ai-standards` for review). Never adds `package.json` `"type"`.
- `init-project` adopt mode uses `adopt.py` instead of `copier copy` (which aborts on conflicts or,
  with `--overwrite`, replaces user files).
- Default template source: `gh:Mustafa212/ai-standards`.
- Projects on 0.1.0: your `CLAUDE.md` is left as it is on update. You can delete its old
  "Claude Code specifics" section, which now lives in `AGENTS.md`.

## 0.1.0

- Initial layers: base rules, TypeScript and Python stacks, orgs `personal` and `example-corp`.
- `[tool]` enforcement: ESLint (strict type-checked) + Prettier, Ruff + mypy strict, coverage
  thresholds, pre-commit (gitleaks, Conventional Commits), CI.
- Claude Code hooks: lint every edited file, block edits to managed files.
- Plugin: `init-project`, `update-standards`, `propose-rule` skills and a SessionStart hook.
- Rule regression tests in `tests/violations/`.
