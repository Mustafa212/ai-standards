# Changelog

Versions follow semver, from the point of view of a project that runs `copier update`:

- **MAJOR**: existing, previously-passing code may now fail checks (stricter threshold, new
  `[tool]` rule that errors). Projects should plan time for the update.
- **MINOR**: new `[review]`/`[ai]` rules, new orgs, stacks or tooling that does not fail existing code.
- **PATCH**: wording, docs, bug fixes in templates.

Each entry names the rule ID, the layer (base / stack / org) and the enforcement level.

## Unreleased

## 0.1.0

- Initial layers: base rules, TypeScript and Python stacks, orgs `personal` and `example-corp`.
- `[tool]` enforcement: ESLint (strict type-checked) + Prettier, Ruff + mypy strict, coverage
  thresholds, pre-commit (gitleaks, Conventional Commits), CI.
- Claude Code hooks: lint every edited file, block edits to managed files.
- Plugin: `init-project`, `update-standards`, `propose-rule` skills and a SessionStart hook.
- Rule regression tests in `tests/violations/`.
