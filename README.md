# ai-standards

One repo that makes every project, every developer and every AI assistant write code the same way:
readable, typed, tested and secure. Rules are **enforced by tools**, not by memory, and they
**evolve** through PRs that reach every project automatically.

```
          base rules            (everyone)
              ▼
   stack: typescript │ angular │ python │ dotnet │ flutter   (per technology)
              ▼
   architecture: simple │ clean │ vertical-slice │ modular-monolith   (.NET; each has its own rules;
                 clean asks: plain │ handlers │ mediator, i.e. whether to use CQRS and a mediator)
              ▼
   org: personal │ example-corp │ …   (per organization: stricter limits, own rules)    ┐ in your
              ▼                                                                         │ private
   project: orgs/<org>/projects/<project>.md   (rules of one project)                   ┘ copy
```

Readability comes first: plain code a new teammate understands on first read, small functions,
clear names, and a doc comment on every exported function and class (enforced by the linters).

## What a generated project gets

| Layer | What enforces it |
| --- | --- |
| Formatting | Prettier / Ruff format / `dotnet format` / `dart format` |
| Readability limits (function size, complexity, params, nesting, file size, magic numbers, naming) | ESLint (+ angular-eslint) / Ruff / Roslyn analyzers + SonarAnalyzer / `very_good_analysis`, thresholds from base or org |
| Types | TypeScript `strict` + type-checked lint (+ Angular `strictTemplates`) / mypy `--strict` / C# nullable, warnings as errors / Dart strict analyzer |
| Tests | Vitest / pytest / xUnit / `flutter test` with a coverage threshold |
| Architecture (.NET) | Architecture tests (ArchUnitNET): Clean Architecture's dependency direction, no ASP.NET Core in Application, no use case calling another; no slice reaching into another feature, no Domain reaching into a feature; no module using another module's implementation, nothing public in a module but its `<Module>Module` class |
| Secrets, commit format | pre-commit (gitleaks, Conventional Commits) |
| The gate | GitHub Actions CI running the same `check` command |
| AI while it writes | Claude Code hooks: lint every edited file and send errors back; block edits to managed files |
| AI instructions | `AGENTS.md` (+ `CLAUDE.md`, Cursor rules, Copilot instructions), composed from the layers |
| Staying current | Monthly workflow opens an "ai-standards update" PR |

## Quick start

### 1. Pick the source

Use this repo as it is (`gh:Mustafa212/ai-standards` is the default source), or fork it and set
your fork in `copier.yml` and `plugin/.claude-plugin/plugin.json`, with its tags pushed (projects
pin to tags and update from them). Your own orgs and project rules never go into a public repo: the
`onboard` skill keeps them in a private copy (see [Orgs and projects](#orgs-and-projects-private)).

### 2. Install the plugin (once per machine)

Prerequisites: `git` and Node 22 (TypeScript stack); `uv` and `make` (Python stack); the .NET 10
SDK (.NET stack); the Flutter SDK (Flutter stack). On Windows:
`winget install astral-sh.uv` and `winget install ezwinports.make`. Without `uv`, the Claude hooks of a
Python project block edits and say why, instead of silently not checking anything.

```bash
claude plugin marketplace add Mustafa212/ai-standards
claude plugin install ai-standards@ai-standards
```

Set the template source when prompted (or later in `/config`). From now on, in any folder that isn't
on the standards yet, Claude is told at session start to use `ai-standards:onboard`, which registers
the project and then scaffolds it (empty folder) or extracts its rules and audits it (existing code).
For a belt-and-braces setup, append `user-level/CLAUDE.md` to `~/.claude/CLAUDE.md`.

For a company: put `extraKnownMarketplaces` + `enabledPlugins` in managed settings so the plugin is
installed on every machine and can't be disabled. Generated projects already include these keys in
`.claude/settings.json`, so anyone who clones one gets the plugin too.

### 3. Start a project

In Claude Code, in an empty folder: *"create a new TypeScript project called billing-api"*. The
`onboard` skill asks which org it belongs to (or creates a new one), registers it, then scaffolds.
Without Claude:

```bash
uvx copier copy --trust gh:Mustafa212/ai-standards my-project
```

### Existing projects

Open Claude Code in a project that isn't on the standards yet and it offers, once, to register it
(`/ai-standards:onboard`): it asks the org, proposes project rules from the code (see below), and
audits the project. Nothing in the project changes. Say no for good and it creates
`.ai-standards-skip`.

| Stack | New project | Rules and audit (existing code) | Full adoption (existing code) |
|---|---|---|---|
| typescript | yes | yes | yes |
| python | yes | yes | yes |
| angular | yes | yes | later |
| dotnet | yes | yes | later |
| flutter | yes | yes | later |

**Several projects in one repository** (e.g. `backend/` and `frontend/`): pre-commit, GitHub
Actions and Claude Code read their config only at the repository root. Each folder is rendered
with `in_workspace=true`, and the root with `stack: workspace`, which holds the one pre-commit
config, CI workflow (a job per folder) and Claude settings, and runs each folder's own checks and
hooks from inside that folder. `/ai-standards:init-project` sets this up.

**Rules and audit** change nothing in the project. The rules stay in your private copy.
`/ai-standards:audit` runs the stack's analyzers in a temporary worktree, AI agents check the
`[review]` rules, and the report goes to `~/.claude/ai-standards/reports/<org>/<project>/`.

**Full adoption** (`/ai-standards:adopt-project`, typescript and python today) adds the tools to the
repository:

1. **Audits** read-only: stack, existing configs, tests, coverage, type errors. Failing tests stop it.
2. **Merges** without overwriting (`scripts/adopt.py`): missing files are added, `package.json` and
   `.claude/settings.json` only gain missing keys, any other differing file gets the standard version
   next to it as `<file>.ai-standards` for you to decide.
3. **Baselines** the old violations (`eslint-suppressions.json` / `# noqa`), in separate commits for
   formatting and baseline, so from day one CI fails on **new** problems only. Type checking can be
   *deferred* and coverage can start at today's value (*floor*); both run in CI as visible warnings.
4. **Writes the plan**, `docs/STANDARDS-DEBT.md`: the baselined debt ordered by risk (P1 correctness
   and security → P4 style), with commands to see each item.

Then `/ai-standards:fix-debt` pays it down in rounds, for adopted and registered projects on every
stack. You approve a round once. Each item is pinned by tests when its code isn't covered, fixed,
and proven by a verdict a script computes: test result files, a canary that shows the tests see the
code, and the analyzer showing the item gone. It gets its own commit, and the round ends in one pull
request. The baseline can only shrink (both linters fail on stale entries), and the settings ratchet
up with `copier update --data coverage_floor=<n> --data 'deferred_checks=[]'`. Debt is never mixed
into feature work (rule ADOPT-2). The edit hook only reports problems on lines you changed, so old
code isn't rewritten as a side effect.

## Orgs and projects (private)

Orgs, projects and their rules belong to whoever uses the plugin, so they never go into this public
repo. They live in a **private copy** of it, which the `onboard` skill sets up once per machine (or
one per client, when one client mustn't see another's rules):

```
Mustafa212/ai-standards        public    base + stacks + template + plugin
        │  upstream: git pull upstream main --tags   (new public releases, after you agree)
        ▼
<you>/ai-standards-<name>      private   + orgs/orgs.yml, orgs/<org>/rules.md, orgs/<org>/projects/*.md
        │  copier copy / update
        ▼
your projects (private repos)  AGENTS.md = base + stack + org + project
```

- **Publishing it:** GitHub has no private forks of public repos, so the copy is a clone with the
  public repo renamed to `upstream`. You publish it from GitHub Desktop (Publish repository, "Keep
  this code private"), or the skill uses `gh` if it's installed. Teammates get access to that repo
  only.
- **Onboarding a project:** pick the org (or create one with its rule prefix, such as `ACME`),
  register the project, scaffold or adopt it. For existing code, Claude sorts what the code does
  into **project rules** (at least 80% consistent, with evidence: `14 of 14 controllers…`),
  **inconsistencies** (two ways of doing one thing), **wrong patterns** (repeated defects, reported
  as findings) and **exception candidates** (consistent, but against a base or stack rule). You
  decide each one: keep, edit or drop a rule; fix or keep an exception, which then replaces that
  rule for this project only (`<PREFIX>-EX-n [exception] → <RULE>`, with the reason).
- **No rule twice:** a proposal already covered by base, stack or org is dropped. One that another
  project of the same org already has is offered for **promotion to the org** (`BILL-4` + `PORT-3` →
  `ACME-5`). `scripts/check_rules.py` fails CI on exact duplicates inside an org.
- **Refresh:** after 7 days and 5 commits since the last analysis, Claude offers to look at what
  changed: new patterns, and project rules the code stopped following.
- **Ask first:** nothing is saved, committed, pushed or updated without your yes. Rules that would
  help everyone go to this public repo as a PR (`propose-rule`), never org or project data.

### Which files are whose

- **Yours, never touched by updates:** `CLAUDE.md` (only the `@AGENTS.md` line is guaranteed),
  `README.md`, `docs/PROJECT.md`, `docs/STANDARDS-DEBT.md`, `package.json`, `pyproject.toml`,
  `.gitattributes`. The
  standard scripts in `package.json` just call `.ai-standards/run.mjs`, so updates never need to
  change your manifest or collide with your dependencies.
- **Managed by the standards:** lint/type/test configs, CI, `AGENTS.md`, `.ai-standards/`,
  `.claude/settings.json`, hooks, `Makefile`. AI edits to them are blocked. Personal Claude
  settings belong in `.claude/settings.local.json`.
- **`.ai-session/`** (local AI working state, e.g. from a senior-dev workflow) is git-ignored and
  skipped by every linter and hook.

## Changing the rules

| I want to… | Edit |
| --- | --- |
| Change a threshold for everyone | `config/defaults.jinja` |
| Change a threshold for one org | `orgs/<org>/settings.jinja` |
| Add a rule for everyone | `rules/base.md` (+ lint config if a tool can check it) |
| Add a rule for one stack | `rules/stacks/<stack>.md` (+ that stack's lint config) |
| Add a rule for one org | `orgs/<org>/rules.md` (+ `settings.jinja`, e.g. banned imports) |
| Add a rule for one project | `orgs/<org>/projects/<project>.md` in your private copy (or let `onboard` propose it) |
| Show the auditors what breaking a `[review]` rule looks like | `rules/examples/<rule file's name>` (or `orgs/<org>/examples.md`); never rendered into AGENTS.md |
| Add an org | `/ai-standards:onboard` (it adds `orgs/<org>/` and the choice in `orgs/orgs.yml`) |
| Change which rule a tool's check belongs to | `config/tool-map.json` (or `orgs/<org>/tool-map.json`) |
| Change how urgent a rule is in audits (P1–P4) | `config/rule-priority.json` (or `orgs/<org>/rule-priority.json`); `tool_ids` overrides one check |
| Add a stack | `rules/stacks/<stack>.md`, template files named `{% if stack == '<stack>' %}…{% endif %}`, a choice in `copier.yml`, a branch in `scripts/test-templates.sh` |
| Add an architecture | `rules/architectures/<stack>-<architecture>.md`, its template folders, a choice in `copier.yml`, its loop entry in `scripts/test-templates.sh` |

Or just tell Claude what keeps going wrong; the `ai-standards:propose-rule` skill turns it into a
PR. Every PR runs `scripts/test-templates.sh`, which generates all stack × org projects, checks they
pass, checks that every rule in `tests/violations/` still fires, exercises the Claude hooks
(`scripts/test-hooks.sh`), adopts a messy legacy project end to end, ratchet included
(`scripts/test-adopt.sh`), and audits an existing project of every stack without changing it
(`scripts/test-audit.sh`). See
[docs/EVOLVING.md](docs/EVOLVING.md) for the full loop and versioning.

## Repo layout

```
copier.yml                 questions (org, stack, name, AI tools)
config/                    default thresholds + resolution, tool-map.json (tool check → rule), rule-priority.json
rules/                     base and per-stack rule text (becomes AGENTS.md)
orgs/orgs.yml              the org question (a private copy lists its own orgs here)
orgs/<org>/                settings.jinja (overrides) + rules.md (extra rules) + projects/ (private copy)
partials/                  composes base + stack + org into one rules body
template/                  files rendered into each project
plugin/                    Claude Code plugin: skills, the rule-auditor agent, SessionStart hook
.claude-plugin/            marketplace manifest (this repo is installable as a marketplace)
tests/violations/          code that must be rejected, per stack and org
scripts/test-templates.sh  end-to-end test of every combination
scripts/audit.py           runs a stack's analyzers in a temporary worktree and writes the audit report
scripts/check_rules.py     no rule written twice inside an org; every exception targets a real rule
user-level/CLAUDE.md       optional snippet for ~/.claude/CLAUDE.md
```

## Limits worth knowing

- Instructions to AI tools are guidance; the hard guarantee is pre-commit + CI. Protect `main` with
  required status checks so CI is actually a gate.
- Hooks run only in Claude Code. Other AI tools get the instruction files, and their output is
  stopped at pre-commit and CI.
- The managed-file guard stops Claude's edit tools, not shell commands and not humans (humans can
  run `AI_STANDARDS_UNLOCK=1 claude`). CI runs the configs from the PR itself, so the hard rule is
  CODEOWNERS on the managed files (see `.claude/managed-files.txt`) plus required review on `main`.
- The monthly update PR needs a secret `AI_STANDARDS_TOKEN` in each project (Contents, Pull requests
  and Workflows read/write). With only the default `GITHUB_TOKEN`, GitHub refuses updates that touch
  `.github/workflows/` and doesn't run CI on the PR.
