---
name: propose-rule
description: Use when a rule should be added, changed or removed in ai-standards: the same review comment or AI mistake appears twice, the user says "we should always/never ...", a managed file blocks a needed change, or an incident reveals a missing check.
---

# Propose a rule change to ai-standards

Rules evolve through pull requests to the standards repo (`${user_config.standards_source}`),
never by editing a project's managed files.

## 1. Shape the rule

Write down, and confirm with the user:

- **Problem**: what went wrong, with a real example (link or snippet).
- **Rule**: one sentence, imperative.
- **Layer**: `base` (everyone), `stack` (all TS or all Python projects) or `org` (one org).
  Default to the narrowest layer that covers the problem.
- **Enforcement**, strongest that is practical:
  1. `[tool]`: an existing lint rule (ESLint, typescript-eslint, Ruff, mypy), a config setting,
     a CI step or a hook. Prefer this. Name the exact rule.
  2. `[review]`: a reviewer can check it, a tool cannot.
  3. `[ai]`: guidance on how to work.
- **Good / bad example**: two short snippets.
- **Impact**: will existing projects fail checks after updating? That makes it a breaking change.

## 2. Edit the standards repo

Clone it to a temp dir and create a branch `rule/<short-name>`. Then edit:

| Change | Files |
| --- | --- |
| Rule text | `rules/base.md`, `rules/stacks/<stack>.md` or `orgs/<org>/rules.md` |
| Threshold | `config/defaults.jinja` (base) or `orgs/<org>/settings.jinja` (org) |
| New setting | add to `config/defaults.jinja` **and** `config/settings.jinja` |
| Lint rule | `template/...eslint.config.js...jinja` or `template/...ruff.toml...jinja` |
| New org | copy `orgs/personal/`, then add it to the `org` choices in `copier.yml` |

Give the rule the next free ID in its section (e.g. `RDB-8`). Keep wording short; every line in
AGENTS.md costs context in every session.

Add a CHANGELOG entry under `## Unreleased` with the rule ID, layer and enforcement level, and mark
it **BREAKING** if existing code may fail the new check.

## 3. Prove it

Run `scripts/test-templates.sh` in the standards repo. It generates every stack × org combination
and runs each project's full check. For a new `[tool]` rule, also confirm it actually fires: add a
case to `tests/violations/` that breaks the rule (see that folder's README).

## 4. Open the PR

Ask the user before pushing or opening the PR. Title: `feat(rules): <rule>` (or `fix(rules):`,
`chore(rules):` for removals). In the body: problem, rule, layer, enforcement, examples, impact.
