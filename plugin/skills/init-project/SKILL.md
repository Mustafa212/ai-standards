---
name: init-project
description: Use first, before writing any file or running a scaffolding command (npm init, uv init, dotnet new, flutter create, ng new), whenever the user wants to create, start, init, bootstrap or scaffold a NEW project or repo. For an existing project, use adopt-project instead.
---

# Scaffold a project from ai-standards

The template is the single source of truth. Your job is to collect answers and run it, not to
write configuration yourself. Never hand-write eslint, prettier, tsconfig, ruff, mypy, pytest,
pre-commit or CI files; if the template lacks something, finish the scaffold and then offer the
`propose-rule` skill.

Template source (`<source>` below): the `Source:` line of `~/.claude/ai-standards/config.md`
(the user's private copy, set up by the `onboard` skill) if that file exists, else
`${user_config.standards_source}`. Default org: `${user_config.default_org}`.
Usually the `onboard` skill runs this one, after it has asked the org and registered the project.

## 1. Collect answers

Ask in one go (use AskUserQuestion when available), skipping anything the user already said:

- **org**: which org's rules apply. Default `${user_config.default_org}`.
- **stack**: `typescript`, `angular`, `python`, `dotnet` or `flutter`.
- **architecture** (dotnet only): `simple` (one Web API project), `clean` (Domain, Application,
  Infrastructure, Api) or `vertical-slice` (one folder per use case). Recommend `simple` for small
  services; each architecture adds its own rules to `AGENTS.md`.
- **project_name**: human-readable name.
- **description**: one line (optional).
- **ai_tools**: any of `claude`, `cursor`, `copilot` (AGENTS.md is always generated).

To see which orgs and stacks exist, read `orgs/orgs.yml` and `copier.yml` in the template source
(for a `gh:` source: `git clone --depth 1 https://github.com/<owner>/<repo> <tmp dir>`).
If the user names an org that does not exist, say so and offer `personal`; do not invent one.

## 2. Run the template

Commands use `uvx copier`; when it isn't available, see `${CLAUDE_PLUGIN_ROOT}/references/runners.md`.

New project (current directory empty, or a new subdirectory the user named):

```bash
uvx copier copy --trust \
  --data org=<org> --data stack=<stack> \
  --data project_name="<name>" --data description="<description>" \
  --data 'ai_tools=["claude"]' \
  --data standards_source="<source>" \
  "<source>" <target-dir>
```

Use the remote source (not a local clone path) so `copier update` and the monthly update workflow
can reach it later.

If the target directory already contains code, stop and use the `adopt-project` skill instead.
Never run `copier copy` into an existing project and never pass `--overwrite`: it replaces the
user's files.

## 3. Finish setup

Run inside the project:

1. `git init` (if not a repo yet).
2. Install deps: `npm install` (typescript, angular), `uv sync` (python), `dotnet restore` (dotnet,
   needs the .NET 10 SDK) or `flutter pub get` (flutter). A Flutter scaffold has no platform folders
   yet: `flutter create . --project-name <package>` adds them (android, ios, web…) without touching
   `lib/`. Python projects need `uv` and `make` (install commands in `runners.md`); the Claude hooks
   block edits until `uv` is installed.
3. `pre-commit install --install-hooks -t pre-commit -t commit-msg` (install pre-commit with
   `uv tool install pre-commit` or `pipx install pre-commit` if missing).
4. Run the full check: `npm run check` (typescript, angular), `make check` (python) or
   `bash .ai-standards/check.sh` (dotnet, flutter). It must pass on a fresh scaffold. If it does
   not, report the failure; do not edit managed files to make it pass.
5. Offer the commit; committing is the user's call. Suggested message (Conventional Commits, which
   the commit-msg hook enforces): `chore: scaffold from ai-standards`.

## 4. Report

Tell the user, briefly: org, stack, what is enforced (lint, types, coverage threshold, hooks, CI),
where project-specific notes go (`docs/PROJECT.md`), and that standards updates arrive as a monthly
PR (or on demand with the `update-standards` skill). Mention that `CLAUDE.md` is theirs to edit:
ai-standards only guarantees the `@AGENTS.md` line in it.
