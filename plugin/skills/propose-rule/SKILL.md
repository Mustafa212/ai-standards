---
name: propose-rule
description: Use when a rule should be added, changed or removed in ai-standards: the same review comment or AI mistake appears twice, the user says "we should always/never ...", a managed file blocks a needed change, or an incident reveals a missing check.
---

# Propose a rule change to ai-standards

Rules evolve in the standards repos, never by editing a project's managed files. Where a change
goes depends on its layer:

- **General (base, stack):** a pull request to the public repo (`${user_config.standards_source}`).
- **Org or project:** the user's private copy (`<clone>` in `~/.claude/ai-standards/config.md`),
  never the public repo.

Nothing is committed, pushed or opened as a PR without the user's clear yes.

## 1. Shape the rule

Write down, and confirm with the user:

- **Problem**: what went wrong, with a real example (link or snippet).
- **Rule**: one sentence, imperative.
- **Layer**: `base` (everyone), `stack` (all TS or all Python projects), `org` (one org) or
  `project` (one project). Default to the narrowest layer that covers the problem; a rule that two
  projects of an org share belongs to the org.
- **Enforcement**, strongest that is practical:
  1. `[tool]`: an existing lint rule (ESLint, typescript-eslint, Ruff, mypy), a config setting,
     a CI step or a hook. Prefer this. Name the exact rule.
  2. `[review]`: a reviewer can check it, a tool cannot.
  3. `[ai]`: guidance on how to work.
- **Good / bad example**: two short snippets.
- **Impact**: will existing projects fail checks after updating? That makes it a breaking change.

## 2. Edit the standards repo

General change: clone the public repo to a temp dir and create a branch `rule/<short-name>`. Org or
project change: work in `<clone>` (pull first). Then edit:

| Change | Files |
| --- | --- |
| Rule text | `rules/base.md`, `rules/stacks/<stack>.md` or `orgs/<org>/rules.md` |
| Threshold | `config/defaults.jinja` (base) or `orgs/<org>/settings.jinja` (org) |
| New setting | add to `config/defaults.jinja` **and** `config/settings.jinja` |
| Lint rule | `template/...eslint.config.mjs...jinja` or `template/...ruff.toml...jinja` |
| Project rule | `orgs/<org>/projects/<slug>.md` (private copy) |
| New org | the `onboard` skill does it: `orgs/<org>/` from `orgs/personal/`, plus a choice in `orgs/orgs.yml` |

Give the rule the next free ID in its section (e.g. `RDB-10`); org and project rules use their
prefix (`ACME-3`, `BILL-5`), and IDs are never reused. Keep wording short; every line in
AGENTS.md costs context in every session.

Add a CHANGELOG entry under `## Unreleased` with the rule ID, layer and enforcement level, and mark
it **BREAKING** if existing code may fail the new check.

## 3. Prove it

Run `python3 scripts/check_rules.py` (no rule written twice in an org) and `scripts/test-templates.sh`
in the standards repo. It generates every stack × org combination
and runs each project's full check. For a new `[tool]` rule, also confirm it actually fires: add a
case to `tests/violations/` that breaks the rule (see that folder's README).

## 4. Open the PR

Ask the user before pushing or opening the PR. Org and project changes are committed and pushed to
the private copy instead (after the user's yes), then reach projects with `copier update`. Title: `feat(rules): <rule>` (or `fix(rules):`,
`chore(rules):` for removals). In the body: problem, rule, layer, enforcement, examples, impact.
