# Orgs, Projects and Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project rule layer with org promotion and a private-copy onboarding flow, and make readability (doc comments, clear names) tool-enforced. Release 0.4.0.

**Architecture:** The rules stay layered Jinja includes (base → stack → org → project). Org and project files live in the user's private copy of this repo, never in the public one. Duplicates are prevented by the onboard skill (judging meaning) and by `scripts/check_rules.py` in CI (exact matches). SessionStart offers onboarding, and later a refresh when 30 days and 10 commits have passed since the last analysis.

**Tech Stack:** Copier 9.4+ (Jinja, `!include`), bash hooks, Python 3.12 stdlib scripts, ESLint 9 + `eslint-plugin-jsdoc` ^65.3.2, Ruff.

**Spec:** `docs/superpowers/specs/2026-10-13-orgs-projects-readability-design.md`

## Global Constraints

- Org and project data never goes into the public repo. The public repo keeps only `orgs/personal`, `orgs/example-corp` and the example `orgs/orgs.yml`.
- Project file: `orgs/<org>/projects/<project_slug>.md`, rendered into `AGENTS.md` after the org rules.
- Marker line: `<!-- … rules analyzed: YYYY-MM-DD (<sha>|none) -->`. Refresh offer when ≥ **30** days **and** ≥ **10** commits since `<sha>` (`none` = count from the first commit).
- Rule bullet format (what `check_rules.py` parses): `- **<ID> [tool|review|ai]** <text>`.
- IDs: org `<ORGPREFIX>-n`, project `<PROJPREFIX>-n`, never reused; promotion leaves `<!-- moved to org: X-n → Y-m -->`.
- New rules: **RDB-8 [tool]** doc comments (TS `jsdoc/require-jsdoc` publicOnly + `jsdoc/require-description`; Python Ruff `D101`, `D103`; tests exempt). **RDB-9 [review]** names and boolean flags. **TS-6 [tool]** `id-length` `{ min: 2, exceptions: ["i","j","k","x","y","_"], properties: "never" }`. **PY-6 [tool]** Ruff `FBT`.
- Thresholds unchanged. Release 0.4.0, marked **BREAKING**.

## Review Focus

- A project with no project file (unregistered, or a public source) must still render: `ignore missing`. Pinned by the fresh scaffolds in Task 2.
- A marker whose sha isn't in history (rebased, squashed) must not crash the hook: count from the first commit. Pinned in Task 4.
- A project folder that isn't a git repo must not crash the hook or offer a refresh. Pinned in Task 4.
- Prose lines, headings and comment lines in rule files are not rules: `check_rules.py` must ignore them, not crash. Pinned in Task 3.
- The same ID in two different orgs is not a duplicate (orgs never meet in one project); the same ID or text inside one org's scope is. Pinned in Task 3.

---

### Task 1: Org list in its own file

**Files:** Modify `copier.yml`; Create `orgs/orgs.yml`.

**Interfaces:** Produces `orgs/orgs.yml`, a YAML document holding the whole `org:` question. Private copies edit only this file to add orgs.

- [ ] Move the `org:` question out of `copier.yml` into `orgs/orgs.yml` unchanged. In `copier.yml`, split the documents with `---` and add `!include orgs/orgs.yml` before the settings document (Copier's multi-document include).
- [ ] Verify: render `stack=typescript org=example-corp` with copier. The answers file says `org: example-corp`, and `AGENTS.md` has "## Org: example-corp".
- [ ] Commit `refactor: move the org question to orgs/orgs.yml`.

### Task 2: Project rule layer

**Files:** Modify `partials/agents-body.md.jinja` and `scripts/test-templates.sh`.

**Interfaces:** Consumes `org` and `project_slug`. Produces the project section in `AGENTS.md`.

- [ ] Test first: in `test-templates.sh`, after the snapshot is made, write `$work/src/orgs/personal/projects/test-typescript-personal.md` with `## Project: fixture`, a marker line and `- **FIX-1 [review]** Fixture rule.` Then assert that `grep -q 'FIX-1' "$work/typescript-personal/AGENTS.md"` holds and that `example-corp` projects don't contain it.
- [ ] Add `{% include ["orgs/" ~ org ~ "/projects/" ~ project_slug ~ ".md"] ignore missing %}` after the org include.
- [ ] Verify locally: render both slugs. Only the matching one has `FIX-1`, and both render.
- [ ] Commit `feat: project rule layer (orgs/<org>/projects/<slug>.md)`.

### Task 3: Duplicate check

**Files:** Create `scripts/check_rules.py`; Modify `.github/workflows/test-templates.yml` (shell job) and `scripts/test-templates.sh`.

**Interfaces:** `python3 scripts/check_rules.py [root]`: prints one line per problem and exits 1 if any, 0 if none. Scope per org = `rules/base.md` + `rules/stacks/*.md` + `orgs/<org>/rules.md` + `orgs/<org>/projects/*.md`.

- [ ] Test first (`test-templates.sh`): the repo passes. A copy with `- **ME-1 [review]** Same text.` in both `orgs/personal/rules.md` and a personal project file fails with "duplicate text". The same ID in `orgs/personal/rules.md` and `orgs/example-corp/rules.md` passes. A file of only headings and prose passes.
- [ ] Implement with the stdlib: bullet regex `^- \*\*([A-Z][A-Z0-9]*-\d+) \[(tool|review|ai)\]\*\* (.+)$`; text normalized to lowercase alphanumerics with single spaces; report `duplicate id <ID>: <file>, <file>` and `duplicate text: <file> <ID>, <file> <ID>`.
- [ ] Add a step `python3 scripts/check_rules.py` to the CI `shell` job.
- [ ] Commit `feat: check_rules.py rejects duplicate rules within an org`.

### Task 4: SessionStart: onboard offer and refresh offer

**Files:** Modify `plugin/hooks/session-start.sh`; Create `scripts/test-session-start.sh`; call it from `test-templates.sh`.

**Interfaces:** Consumes the marker line in `AGENTS.md`. Produces the offer text, which names `ai-standards:onboard`.

- [ ] Test first (`test-session-start.sh`, plain bash, fixtures in a temp dir). Each case pins its expected output:
  - Marker 40 days old plus 12 commits since its sha → output contains `refresh`.
  - A fresh marker (today) → no `refresh`.
  - A marker sha that isn't in history plus 12 commits → `refresh`.
  - `(none)` plus 3 commits → no `refresh`.
  - A non-git folder with an old marker → exit 0 and no `refresh`.
  - An unregistered folder with `package.json` → output contains `ai-standards:onboard`.
  - An empty folder → `ai-standards:onboard`.
- [ ] Implement: constants `REFRESH_DAYS=30`, `REFRESH_COMMITS=10`; `days_since <YYYY-MM-DD>` (GNU `date -d`, falling back to BSD `date -j -f %Y-%m-%d`); commit count via `git -C "$project_dir" rev-list --count`, falling back to the full count when the sha is unknown. The adoption and empty-folder messages point to `ai-standards:onboard`; the compact skip stays.
- [ ] Commit `feat(plugin): onboarding offer and periodic rule refresh offer`.

### Task 5: Readability rules, enforced

**Files:** Modify `rules/base.md`, `rules/stacks/typescript.md`, `rules/stacks/python.md`, the `eslint.config.mjs` and `ruff.toml` templates, `package.json.jinja`, `run.mjs.jinja`, both `greeting` sample files, both Python hook files, `tests/violations/typescript/readability.ts`, `tests/violations/python/readability.py`.

- [ ] Test first: extend the expect lines. TS gets `id-length, jsdoc/require-jsdoc`. Python gets `D103, FBT001`, with `def notify(user: str, urgent: bool) -> None:` (body `...`) added to the Python file.
- [ ] `base.md`: move section 2 (Readability) above "Before writing code"; RDB-7 becomes the first bullet with the spec's wording; add RDB-8 and RDB-9 with the spec's wording. Stack files: add TS-6 and PY-6.
- [ ] ESLint: import `eslint-plugin-jsdoc`, set `jsdoc/require-jsdoc` (`publicOnly: true`; `FunctionDeclaration`, `ClassDeclaration`, `ArrowFunctionExpression`, `FunctionExpression` true), `jsdoc/require-description`, and `id-length` as in Global Constraints; the test-files override turns both jsdoc rules off. Ruff: add `"D101"`, `"D103"`, `"FBT"` to `select`, and `"D"` to `tests/**` ignores. Add `"eslint-plugin-jsdoc": "^65.3.2"` to `package.json.jinja` devDependencies and to `REQUIRED_DEV_DEPENDENCIES`.
- [ ] Doc comments: `buildGreeting` / `build_greeting`, and every public function in `check_edited_file.py` and `protect_managed_files.py`.
- [ ] Verify locally: fresh TS and Python scaffolds pass their full check, and the violation files fire the new IDs.
- [ ] Commit `feat(rules)!: readability first (RDB-8 doc comments, RDB-9, TS-6, PY-6)`.

### Task 6: The onboard skill and the source lookup

**Files:** Create `plugin/skills/onboard/SKILL.md`; Modify `init-project`, `adopt-project`, `update-standards`, `propose-rule`.

**Interfaces:** `~/.claude/ai-standards/config.md` with the lines `Source: gh:<owner>/<repo>` and `Clone: <absolute path>`. All skills: source = that `Source:` line, otherwise `${user_config.standards_source}`.

- [ ] `onboard/SKILL.md`: the six steps of spec section 2, the refresh mode of section 3, and the promotion rules of section 4, each gated by the user. It says that commits and pushes to the private copy need the user's OK, and that `check_rules.py` runs before every commit.
- [ ] The other skills: point to the source lookup; `propose-rule` routes base/stack changes to the public repo (owner pushes, anyone else sends a PR) and org/project changes to the private copy.
- [ ] Verify: `claude plugin validate ./plugin` passes.
- [ ] Commit `feat(plugin): onboard skill with private org copy, rule analysis and promotion`.

### Task 7: Docs and release

**Files:** `README.md`, `docs/EVOLVING.md`, `CHANGELOG.md` (0.4.0, BREAKING), `plugin/.claude-plugin/plugin.json` (0.4.0).

- [ ] Docs: private copy (why, how to publish, `git pull upstream main`), onboarding, the project layer, promotion.
- [ ] Push `main`; CI green (test both stacks, shell, plugin); tag `v0.4.0`; release job green.
