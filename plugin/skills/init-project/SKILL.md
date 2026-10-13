---
name: init-project
description: Use whenever the user wants to create, start, init, bootstrap or scaffold a new project or repo, or to adopt shared standards in an existing one. Scaffolds from the ai-standards template so lint, formatting, types, tests, CI and AI rules are identical across projects. Use this instead of hand-writing configs.
---

# Scaffold a project from ai-standards

The template is the single source of truth. Your job is to collect answers and run it, not to
write configuration yourself. Never hand-write eslint, prettier, tsconfig, ruff, mypy, pytest,
pre-commit or CI files; if the template lacks something, finish the scaffold and then offer the
`propose-rule` skill.

Template source: `${user_config.standards_source}`
Default org: `${user_config.default_org}`

## 1. Collect answers

Ask in one go (use AskUserQuestion when available), skipping anything the user already said:

- **org**: which org's rules apply. Default `${user_config.default_org}`.
- **stack**: `typescript` or `python`.
- **project_name**: human-readable name.
- **description**: one line (optional).
- **ai_tools**: any of `claude`, `cursor`, `copilot` (AGENTS.md is always generated).

To see which orgs and stacks exist, read `copier.yml` in the template source
(for a `gh:` source: `git clone --depth 1 https://github.com/<owner>/<repo> <tmp dir>`).
If the user names an org that does not exist, say so and offer `personal`; do not invent one.

## 2. Run the template

Pick a runner: `uvx copier` if `uv` exists, else `pipx run copier`, else `pip install --user copier`.

New project (current directory empty, or a new subdirectory the user named):

```bash
uvx copier copy --trust \
  --data org=<org> --data stack=<stack> \
  --data project_name="<name>" --data description="<description>" \
  --data 'ai_tools=["claude"]' \
  --data standards_source="${user_config.standards_source}" \
  "${user_config.standards_source}" <target-dir>
```

Use the remote source (not a local clone path) so `copier update` and the monthly update workflow
can reach it later.

### Adopt mode (existing project)

Never run `copier copy` into an existing project, and never pass `--overwrite`: it replaces the
user's files, including their `CLAUDE.md`. Use the safe merge instead:

1. Require a clean git tree (`git status`), so every change is reviewable and revertable.
2. Clone the standards repo to a temp dir (`git clone --depth 1 ...`) for its scripts.
3. Render the template into a second, empty temp dir: the command above with that dir as target.
4. Merge: `python3 <standards clone>/scripts/adopt.py <rendered dir> .`
   It never overwrites or deletes. It keeps `CLAUDE.md` and only adds the `@AGENTS.md` line at the
   top, merges `package.json` / `.claude/settings.json` by adding missing keys, appends missing
   `.gitignore` lines, and saves the standard version of any other differing file as
   `<file>.ai-standards` next to the original.
5. Walk the user through the report: each "Kept yours, differs" and "Not added" JSON value
   (e.g. `"type": "module"`, which would break a CommonJS project), and each
   `*.ai-standards` file. Typical decisions: replace an old lint config with the standard one,
   keep a project-specific script. Delete each `*.ai-standards` file once decided.
6. Expect many lint errors in existing code. Offer to fix them in small, separate commits.

## 3. Finish setup

Run inside the project:

1. `git init` (if not a repo yet).
2. Install deps: `npm install` (typescript) or `uv sync` (python).
3. `pre-commit install --install-hooks -t pre-commit -t commit-msg` (install pre-commit with
   `uv tool install pre-commit` or `pipx install pre-commit` if missing).
4. Run the full check: `npm run check` or `make check`. It must pass on a fresh scaffold. If it does
   not, report the failure; do not edit managed files to make it pass.
5. Commit: `git add -A && git commit -m "chore: scaffold from ai-standards"`.

## 4. Report

Tell the user, briefly: org, stack, what is enforced (lint, types, coverage threshold, hooks, CI),
where project-specific notes go (`docs/PROJECT.md`), and that standards updates arrive as a monthly
PR (or on demand with the `update-standards` skill). Mention that `CLAUDE.md` is theirs to edit:
ai-standards only guarantees the `@AGENTS.md` line in it.
