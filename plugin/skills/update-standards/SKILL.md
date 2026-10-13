---
name: update-standards
description: Use when the user wants to pull the latest ai-standards rules into the current project, asks whether standards are outdated, or needs to resolve an "ai-standards update" PR.
---

# Update a project to the latest ai-standards

Only works in a project that has `.copier-answers.yml`. If it is missing, offer the
`adopt-project` skill instead.

1. Make sure the working tree is clean (`git status`). If not, ask the user to commit or stash first.
2. Run `uvx copier update --trust --defaults --conflict rej` (or `pipx run copier ...`).
   To preview without writing, add `--pretend`.
3. Summarize what changed: `git diff --stat`, and read the CHANGELOG of the standards repo for the
   versions between the old and new `_commit` in `.copier-answers.yml`. Call out anything marked
   **BREAKING**.
4. Resolve every `*.rej` file. Managed files take the new upstream version. Updates never touch the
   project-owned files (`CLAUDE.md` apart from its `@AGENTS.md` line, `README.md`, `docs/PROJECT.md`,
   `docs/STANDARDS-DEBT.md`, `package.json`, `pyproject.toml`). Delete the `.rej` files when done.
5. Install: `npm install` / `uv sync`. If `npm run check` reports missing dev dependencies, run the
   `npm install -D ...` command it prints. Reinstall pre-commit hooks if `.pre-commit-config.yaml`
   changed.
6. Run the full check (`npm run check` / `make check`). A new `[tool]` rule may flag existing code:
   - a handful of findings: fix them in this change;
   - many findings (common after a BREAKING release): baseline them the way adoption does
     (`npx eslint . --suppress-all` / `uv run ruff check . --add-noqa`), regenerate
     `docs/STANDARDS-DEBT.md`, and pay them down with the `fix-debt` skill.
   Never weaken the new rules or edit managed files to get green.
7. Offer the commit: `chore: update ai-standards to <version>`.
