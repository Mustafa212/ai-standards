# Changelog

Versions follow semver, from the point of view of a project that runs `copier update`:

- **MAJOR**: existing, previously-passing code may now fail checks (stricter threshold, new
  `[tool]` rule that errors). Projects should plan time for the update.
- **MINOR**: new `[review]`/`[ai]` rules, new orgs, stacks or tooling that does not fail existing code.
- **PATCH**: wording, docs, bug fixes in templates.

Each entry names the rule ID, the layer (base / stack / org) and the enforcement level.

## Unreleased

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
