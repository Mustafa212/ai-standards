# Orgs, projects and readability: design

Date: 2026-10-13 · Status: draft for review · Target release: 0.4.0 (BREAKING, see section 5)

## Goal

1. Every project gets rules at four levels (base, stack, org, project) with **no rule written twice**.
   Opening Claude in a project that isn't registered asks which org it belongs to, registers it,
   analyzes existing code into proposed project rules the user approves, and moves a rule up to the
   org once two projects share it. Analysis keeps running over time, not only once.
2. The standards put **readability first**: plain code, small units, clear names, and doc comments
   that say what each public function and class is for.

## Decisions taken with the user

- The public repo (`Mustafa212/ai-standards`) holds only general things: base and stack rules,
  the template, the plugin, example orgs. The owner pushes general improvements; anyone else sends
  a PR.
- Orgs, projects and their rules are **private to whoever uses the plugin**. They never go to the
  public repo. Each user (or team) keeps them in a **private copy** of ai-standards.
- Team members see the rules through that private copy (repo access) and through each project's
  `AGENTS.md` (project repos are private).
- Automatic analysis stays on: Claude offers a re-analysis when a project has changed enough.

## 1. Where things live

```
Mustafa212/ai-standards         public    base + stacks + template + plugin + example orgs
        │ upstream (git pull upstream main brings base updates)
        ▼
<owner>/ai-standards-<name>     private   copy of the above + the user's orgs
  orgs/orgs.yml                 the org question (choices); the only file a copy edits outside orgs/<org>/
  orgs/<org>/rules.md           rules shared by projects of this org
  orgs/<org>/settings.jinja     org thresholds, banned imports
  orgs/<org>/projects/<slug>.md rules of one project, plus its registration header
        │ copier copy / update
        ▼
<project repo>                  private   AGENTS.md = base + stack + org + project
```

- GitHub doesn't allow a private fork of a public repo, so the private copy is a clone whose
  `origin` is renamed `upstream`, published as a new private repo (GitHub Desktop: Publish
  repository, "Keep this code private"; or `gh repo create --private` when `gh` exists).
- `copier.yml` includes `orgs/orgs.yml` (`!include`), so pulling upstream changes to `copier.yml`
  doesn't conflict with the user's org list.
- The plugin finds the private copy through `~/.claude/ai-standards/config.md` (written by the
  onboard skill): its remote (`gh:<owner>/ai-standards-<name>`) and its local clone path. Skills
  fall back to the plugin's `standards_source` when the file doesn't exist.
- A project registered in a private org must have a private repo. Onboarding asks; for a public
  repo it stops and explains why.

Project file format (readable by people, parseable by scripts, rendered into `AGENTS.md` as is):

```markdown
## Project: billing-api

<!-- repo: https://github.com/acme/billing-api · stack: typescript · rules analyzed: 2026-10-13 (a1b2c3d) -->

- **BILL-1 [review]** Database access goes through repositories, never from controllers.
- **BILL-2 [tool]** Money is `Decimal`, never `float` (Ruff banned-api).

<!-- moved to org: BILL-3 → ACME-4 -->
```

IDs: org rules use the org's prefix (`ACME-n`), project rules the project's (`BILL-n`). IDs are
never reused; a rule that moves to the org leaves a `moved to org` line behind.

## 2. Onboarding: `/ai-standards:onboard`

New skill, the single entry point. SessionStart offers it once in any project without
`.copier-answers.yml` (this replaces today's adoption offer). Steps, each one gated by the user:

1. **Private copy.** If `config.md` is missing, or points at the public repo: explain why org data
   can't live there, clone it, rename the remote to `upstream`, and walk the user through
   publishing it as private. Write `config.md`.
2. **Org.** "Which org is this project in?" with the orgs from `orgs/orgs.yml` plus "new org". A new
   org asks only for its name and prefix and starts with the base settings (`orgs/<org>/rules.md`,
   an empty `settings.jinja`, a choice in `orgs/orgs.yml`).
3. **Register.** Create `orgs/<org>/projects/<slug>.md` with the header line (repo, stack, date).
4. **Scaffold or adopt.** Empty folder → `init-project`. Existing code → `adopt-project` (audit,
   merge, baseline, debt plan), then step 5.
5. **Analyze into proposed rules** (existing projects). Find what the code does consistently that
   no base, stack or org rule covers: layering and folder structure, how errors travel, the
   libraries used for each concern (HTTP, dates, money, logging, validation), naming conventions,
   test style. Each proposal shows the rule in one sentence, the evidence (how many places follow
   it, 2–3 `file:line` examples, the exceptions) and whether a lint rule can enforce it (`[tool]`)
   or only review (`[review]`). Only patterns followed in most places become proposals; one-offs
   don't. The user picks ✅ keep, ✏️ edit or ❌ drop for each.
6. **No duplicates** (section 4), then **save**: show the diff in the private copy, commit and push
   after the user's OK, then render into the project (`copier copy` for new, `copier update` for
   adopted) so `AGENTS.md` carries the new rules. The header gets `rules analyzed: <date> (<sha>)`.

## 3. Automatic re-analysis

- SessionStart, in a registered project, reads `rules analyzed: <date> (<sha>)` from `AGENTS.md`.
  When it is at least **30 days** old and there are **10 or more commits** since `<sha>`, Claude
  adds one line to its first reply offering `/ai-standards:onboard` to refresh the rules. Both
  numbers are constants at the top of the hook. A new project is registered with
  `rules analyzed: <date> (none)`, so its commits are counted from the first one: once it has grown
  real conventions, it gets the same offer.
- Refresh looks only at what changed since `<sha>`: it proposes new rules, and flags project rules
  the new code keeps breaking (the rule may be out of date: keep, edit or delete). Then it runs the
  promotion check across the org and updates the marker. Nothing changes without the user's OK.

## 4. No duplicates

- **While saving (the skill, judging meaning):** a proposal already covered by base, stack or org is
  dropped. A proposal that matches a rule in **another project of the same org** is offered for
  promotion: it becomes `ACME-n` in the org file, and both projects drop it (leaving a `moved to
  org` line). Every affected project gets the change on its next `copier update`.
- **In CI (a safety net, exact matches):** new `scripts/check_rules.py` reads every rule bullet in
  `rules/`, `orgs/*/rules.md` and `orgs/*/projects/*.md`. It fails on a duplicate ID, or on the same
  rule text (case and punctuation ignored) in two files. It runs in this repo's CI, which private
  copies inherit.

## 5. Readability first

Rule changes (`rules/base.md` and the stack files):

- The readability section moves up to come right after "Definition of done", and RDB-7 becomes the
  lead rule: *write code a new teammate understands on first read; plain steps over clever
  one-liners; if code needs a comment to say what it does, simplify the code first.*
- **RDB-8 [tool] (new)** Every exported function and class starts with a doc comment (JSDoc
  `/** … */` or a docstring) saying what it is for and anything a caller must know. One sentence is
  enough; tests are exempt. TypeScript: `eslint-plugin-jsdoc` `require-jsdoc` (`publicOnly`) and
  `require-description`. Python: Ruff `D101`, `D103`.
- **RDB-5 [review] (unchanged)** Comments explain *why* (business rules, workarounds, non-obvious
  choices), never restate the code.
- **RDB-9 [review] (new)** No unclear names (single letters outside short loops) and no boolean flag
  arguments (`send(user, true)` → an options object or two functions). Tool-enforced where the stack
  can: **TS-6 [tool]** ESLint `id-length` (min 2; `i`, `j`, `k`, `x`, `y`, `_` allowed; properties
  not checked). **PY-6 [tool]** Ruff `FBT` (boolean positional arguments).
- Thresholds stay as they are (40 lines, complexity 10, 4 parameters, depth 3, 300-line files).
  They're already strict, and an org can tighten them.

Template code follows the new rules (doc comments on the sample code and the Python hooks).
**BREAKING:** existing code without doc comments, or with one-letter names or boolean flag arguments,
fails the new checks after `copier update`. Adopted projects baseline them, the same as at adoption.

## 6. Changes by file

| Area | Files |
| --- | --- |
| Org list | `copier.yml` (`!include orgs/orgs.yml`), new `orgs/orgs.yml` |
| Project layer | `partials/agents-body.md.jinja` (include `orgs/<org>/projects/<slug>.md` if present) |
| Duplicate check | new `scripts/check_rules.py`, step in `.github/workflows/test-templates.yml` |
| Readability | `rules/base.md`, `rules/stacks/*.md`, ESLint and Ruff templates, `package.json` + `run.mjs` (`eslint-plugin-jsdoc`), sample code, Python hooks, `tests/violations/*` |
| Plugin | new `plugin/skills/onboard/SKILL.md`; `session-start.sh` (onboard offer, re-analysis offer); `init-project`, `adopt-project`, `propose-rule`, `update-standards` read the source from `config.md` and know the project layer |
| Docs | `README.md` (private copy, onboarding), `docs/EVOLVING.md` (project layer, promotion), `CHANGELOG.md` 0.4.0, plugin 0.4.0 |

## 7. Testing

- `test-templates.sh`: a fixture project file in the snapshot must appear in the rendered
  `AGENTS.md`; fresh scaffolds of every stack × org still pass their full check with the new rules;
  the violation files declare the new rule IDs, and those rules must fire.
- `check_rules.py` runs on the repo (must pass) and on a fixture with a planted duplicate (must
  fail).
- `session-start.sh`: one fixture with an old marker and enough commits gets the refresh offer; one
  with a fresh marker doesn't.

## Out of scope (later)

- .NET, Angular and Flutter stacks. These are the user's main work projects, so they come next, as
  their own feature.
- Creating the private GitHub repo automatically without `gh` (publishing stays one manual click).
- Meaning-based duplicate detection in CI (the skill does that; CI catches exact matches).
