---
name: update-standards
description: Use when the user wants to pull the latest ai-standards rules into the current project, asks whether standards are outdated, or needs to resolve an "ai-standards update" PR.
---

# Update a project to the latest ai-standards

Only works in a project that has `.copier-answers.yml`. If it is missing, offer the
`init-project` skill in adopt mode instead.

1. Make sure the working tree is clean (`git status`). If not, ask the user to commit or stash first.
2. Run `uvx copier update --trust --defaults --conflict rej` (or `pipx run copier ...`).
   To preview without writing, add `--pretend`.
3. Summarize what changed: `git diff --stat`, and read the CHANGELOG of the standards repo for the
   versions between the old and new `_commit` in `.copier-answers.yml`.
4. Resolve every `*.rej` file. Rule: managed files take the new upstream version; project-owned
   content (dependencies, source, `CLAUDE.md`, `docs/PROJECT.md`) keeps the project's version.
   Copier never overwrites `CLAUDE.md`; it only re-adds the `@AGENTS.md` line if it was removed. Delete the `.rej`
   files when done.
5. Reinstall deps and hooks if lockfiles or `.pre-commit-config.yaml` changed.
6. Run the full check (`npm run check` / `make check`). New rules may flag existing code: fix it,
   or for a large backlog, propose fixing it in follow-up commits. Never weaken the new rules.
7. Commit: `chore: update ai-standards to <version>`.
