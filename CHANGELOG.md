# Changelog

Versions follow semver, from the point of view of a project that runs `copier update`:

- **MAJOR**: existing, previously-passing code may now fail checks (stricter threshold, new
  `[tool]` rule that errors). Projects should plan time for the update.
- **MINOR**: new `[review]`/`[ai]` rules, new orgs, stacks or tooling that does not fail existing code.
- **PATCH**: wording, docs, bug fixes in templates.

Each entry names the rule ID, the layer (base / stack / org) and the enforcement level.

## 0.9.1 — 2026-10-16

- **Rules in effect for a registered, not adopted project:** the audit keeps the rendered rules as
  `RULES.md` in the report folder, and the session-start hook tells Claude to read that file before
  the first edit (or says no rendered rules exist yet, and that the audit renders them). Why: the
  hook said to follow the base, stack and org rules but gave no file Claude could read, and the
  audit deleted its rendered copy.
- **adopt-project vs audit:** adopt-project's description now says it writes to the repository and
  sends read-only checks to audit. Why: both claimed "audit", so "audit my project" could start the
  skill that writes.
- **Docs (PATCH):** the README describes onboarding of existing code (rule sorting, exceptions), the
  audit files, the 7-day refresh and choosing a source; `user-level/CLAUDE.md` points to `onboard`;
  the plugin description covers existing projects.
- **CI (no project impact):** a release fails when its tag doesn't match `plugin.json`, and its notes
  are the version's CHANGELOG section instead of GitHub's generated list.

## 0.9.0 — 2026-10-15

Rules and audit for any existing project, without adoption (part 1 of 3; batch debt fixing and full
adoption for angular, dotnet and flutter come next).

- **Onboard any stack:** typescript, python, angular, dotnet and flutter projects are registered and
  their rules extracted from the code without adopting them; nothing in the project changes.
  Patterns are sorted into rules (at least 80% consistent), inconsistencies, wrong patterns and
  exception candidates. A project exception (`<PREFIX>-EX-n [exception] → <RULE>`, with a reason)
  replaces a base or stack rule for that project; `check_rules.py` checks its target exists.
- **`/ai-standards:audit`:** the stack's real analyzers run with the standard configs in a throwaway
  git worktree (`scripts/audit.py`), read-only `rule-auditor` agents check the `[review]` rules
  with evidence and counts, and a prioritized report is written to `~/.claude/ai-standards/reports/`
  with items per rule and folder and the change since the last audit.
- **Priorities come from the rule** (`config/rule-priority.json`, via `config/tool-map.json`) in the
  audit and in the adoption debt plan, so Sonar `S…` IDs are no longer filed as security. A tool ID
  can have its own priority (`tool_ids`, which an org can override) when its rule mixes concerns:
  `prefer_const_constructors` and `import type` are P4 inside P1 rules, and "no print" is P4 on
  every stack.
- **SessionStart:** offers onboarding for dotnet (a solution up to two levels down), angular and
  flutter projects; summarizes a registered project's latest report; offers the rule refresh after
  7 days and 5 commits (was 30 and 10).
- **Update PR (template, PATCH):** `copier update --conflict inline`, so conflicts show in the PR,
  and the job fails after opening it; `.rej` files, which `.gitignore` hid, are gone.

## 0.8.0 — 2026-10-14

- **CI (no project impact):** the release job skips a tag whose release already exists, instead of
  failing the run (v0.7.0 was published by hand first, so its run went red with every test green).

## 0.7.0

New stacks for new projects (adopting existing ones comes later): **Angular** and **Flutter**.

- **Angular 22** (`stack=angular`): standalone components, signals, `inject()` and feature folders, as
  in the Angular style guide. `AGENTS.md` holds the TypeScript rules (TS-3 and TS-5 have Angular
  wording) plus **NG-1..NG-10**. ESLint shares its TypeScript rules with the typescript stack
  (`partials/eslint-typescript-rules.jinja`) and adds angular-eslint, template rules included.
  `ng build` (with `strictTemplates`) is the type check; `ng test` runs Vitest with the coverage
  threshold (`vitest-base.config.mts`). Angular 22 made OnPush the default, so **NG-1** now forbids
  opting out (`ChangeDetectionStrategy.Eager`).
- **Flutter 3.47 / Dart 3.13** (`stack=flutter`): MVVM as in the Flutter architecture guide (views,
  view models, services), with a fake clock in the tests. **DART-1..DART-10**; `very_good_analysis`
  plus `public_member_api_docs` (RDB-8), `avoid_positional_boolean_parameters` (RDB-9),
  `no_default_cases` (DES-7). Lines are 100 columns (`formatter.page_width`). `check.sh` runs format,
  `flutter analyze --fatal-infos`, the file-length check (RDB-2) and `flutter test` with the coverage
  threshold. RDB-1 and RDB-4 have no free Dart analyzer rule, so they read `[review]` for Flutter.
- Both stacks: Claude hooks (Node for Angular, bash for Flutter), CI jobs, pre-commit, managed files,
  violation tests for every `[tool]` rule, and a CI matrix entry.

## 0.6.0

New stack: **.NET (C#)** for new projects. Adopting existing .NET projects comes later (rules and audit in 0.9.0, full adoption after).

- `stack=dotnet` scaffolds a .NET 10 solution. A new **architecture** layer sits between the stack
  and the org, chosen at scaffold time, and each architecture has its own rules in `AGENTS.md`:
  - `simple`: one Web API project and its tests (API-1, API-2).
  - `clean`: Domain, Application, Infrastructure, Api. **CLEAN-1 [tool]**: architecture tests keep
    dependencies pointing inward.
  - `vertical-slice`: `Features/<Feature>/<UseCase>/`. **VSA-2 [tool]**: architecture tests stop a
    feature from depending on another.
- Stack rules **CS-1..CS-14** (approved in `docs/research/2026-10-13-dotnet-angular-flutter-rules.md`).
  CS-1..CS-7 are enforced by the build: a managed `Directory.Build.props` (nullable, warnings as
  errors, `latest-Recommended` analyzers, code style in the build, XML docs) and `.editorconfig`.
  IDE0049 never runs in a build, so "keywords over runtime type names" moved from CS-2 to
  **CS-14 [review]**.
- The base readability rules are tool-enforced in .NET too, through **SonarAnalyzer.CSharp** (S107,
  S138, S1541, S134, S104, S109, S125). Thresholds come from base or org settings, through a managed
  `.ai-standards/SonarLint.xml`.
- Org banned APIs for .NET (`banned_cs`, BannedApiAnalyzers RS0030); example-corp bans `HttpClient`
  in production code (EC-1).
- Tests: xUnit v3 on Microsoft.Testing.Platform, coverage with `coverlet.MTP` and the org threshold,
  and a fake `TimeProvider` (TST-4).
- `bash .ai-standards/check.sh` is the check (format, build, test). The Claude hooks are bash
  without jq: they block managed files and format every edited `.cs` file.
- `test-templates.sh` covers 3 architectures × every org: a fresh scaffold passes, every `[tool]`
  rule fires (`tests/violations/dotnet/`), the hooks work, and a planted cross-feature reference
  fails VSA-2. CI adds `dotnet` to the matrix.
- `DES-5`, `DES-7`, `RDB-1` and `RDB-8` now have .NET wording.

## 0.5.0

New `[review]` rules (base), from the research in `docs/research/2026-10-13-dotnet-angular-flutter-rules.md`,
approved by the owner:

- **DES-5 [review]** Data is immutable by default.
- **DES-6 [review]** The UI shows state and forwards events; business logic lives below it.
- **DES-7 [review]** Switches over an enum or union handle every case, with no catch-all default.
- **RDB-10 [review]** Files are named after what they hold; no `utils`, `helpers` or `common`.
- **ERR-5 [review]** Error messages say what happened and what to do next.
- **TST-4 [review]** Tests never rely on timing; fakes over mocks.

## 0.4.0

**BREAKING:** readability rules now fail lint on existing code without doc comments, with one-letter
names (TypeScript) or with boolean positional arguments (Python). Fix or baseline them (see the
`update-standards` skill).

Readability first (base and stacks):

- The readability section comes right after "Definition of done". **RDB-7 [review]** leads it: code a
  new teammate understands on first read, plain steps over clever one-liners.
- **RDB-8 [tool]** (base) Exported functions and classes start with a doc comment.
  `eslint-plugin-jsdoc` (`require-jsdoc` publicOnly, `require-description`); Ruff `D101`, `D103`.
- **RDB-9 [review]** (base) Clear names, no boolean flag arguments. **TS-6 [tool]** (stack:
  typescript) ESLint `id-length`. **PY-6 [tool]** (stack: python) Ruff `FBT`.

Orgs and projects:

- New **project layer**, `orgs/<org>/projects/<slug>.md`, rendered into `AGENTS.md` after the org.
- Orgs and projects live in the user's **private copy** of ai-standards, never in the public repo.
  The org question moved to `orgs/orgs.yml` (`!include`), so pulling upstream never conflicts with
  a private copy's orgs.
- New **`onboard` skill**: sets up the private copy, asks the org (or creates one), registers the
  project, scaffolds or adopts it, proposes project rules from the code with evidence, and promotes
  a rule shared by two projects to the org. Refresh mode looks at what changed since the last
  analysis.
- SessionStart offers onboarding in unregistered projects, offers a refresh after 30 days and 10
  commits, and tells Claude never to apply a standards change without asking.
- New `scripts/check_rules.py` (in CI): no duplicate rule ID or text inside an org.
- `propose-rule` routes general rules to the public repo as a PR and org or project rules to the
  private copy. `update-standards` asks before writing anything.
- Release `v0.3.1` follow-up: `test-templates.sh` is clean on older shellcheck versions.

## 0.3.1

Fixes (no rule changes):

- **Monthly update PRs:** `create-pull-request` uses the `AI_STANDARDS_TOKEN` secret when set. With the
  default `GITHUB_TOKEN`, GitHub refused updates that touched `.github/workflows/` and never ran CI
  on the PR; the workflow now warns when the secret is missing.
- **Line endings:** `.gitattributes` (`* text=auto eol=lf`) in this repo and in generated projects
  (project-owned, line-merged on adopt). On Windows with `core.autocrlf=true`, clones got CRLF and
  `prettier --check` failed on every file.
- **Python hooks fail closed:** without `uv` they block the edit and say how to install it, instead of
  failing to start (which Claude Code treats as non-blocking, so managed files were unprotected).
  The managed-files hook runs with `--no-project`. The edit hook no longer skips files whose names
  start with `dist` (e.g. `distance.py`), and says how to install ruff when it's missing.
- **Python dev tools:** `make check` first checks that mypy, pytest, pytest-cov and ruff are installed
  and prints the `uv add --dev ...` command (adopted projects keep their own `pyproject.toml`).
  `pytest.ini` sets `pythonpath = src`, so projects that aren't installed as a package still import.
  pre-commit runs the project's own ruff instead of a separately pinned copy, so pre-commit, the edit
  hook and CI agree.
- **TypeScript:** `eslint.config.js` → `eslint.config.mjs`, so it loads in CommonJS projects too (adopt
  never adds `"type": "module"`). `copier update` removes the old file.
- **Plugin:** the adoption offer isn't repeated after a compaction. `adopt-project` checks the test runner
  (Vitest only; Jest suites are migrated first), module system and Python layout, installs the
  standard Python dev tools into a kept `pyproject.toml`, and works where `python3` is the Windows
  Store alias.
- **This repo:** CI calls `bash scripts/test-templates.sh` (immune to lost executable bits), and tag
  pushes now trigger the release job. The adopt e2e test keeps the legacy `pyproject.toml`, as users
  do, instead of replacing it.
- `AGENTS.md`: managed files must not be changed through shell commands either. README: prerequisites,
  the update token, and CODEOWNERS as the hard guard.

## 0.3.0

Existing projects:

- New `adopt-project` skill: read-only audit → approved plan → safe merge → format-only commit →
  lint baseline (`eslint-suppressions.json` / `ruff --add-noqa`) → debt plan. CI enforces new code
  from day one.
- New `fix-debt` skill and `scripts/standards_audit.py`, which writes `docs/STANDARDS-DEBT.md`: the
  baselined debt ordered P1 (correctness, security) → P4 (style), with commands to see each item.
- New answers `adopted`, `deferred_checks` (typecheck, coverage) and `coverage_floor` (ratchet).
  Deferred checks run in CI as non-blocking warnings. `AGENTS.md` gets an "Adoption status"
  section and rules ADOPT-1..3 (new lines clean; debt never mixed into feature work; baseline only
  shrinks).
- SessionStart offers adoption once in unadopted projects (opt out with `.ai-standards-skip`), and
  reports the debt summary in adopted ones.

Fixes:

- **`package.json` and `pyproject.toml` are now project-owned** (`_skip_if_exists`). Before,
  `copier update` could replace them with the template's version and move the project's own
  dependencies into a `.rej` file. Standard scripts delegate to the managed
  `.ai-standards/run.mjs`, which checks required dev dependencies and prints the install command.
- **Edit hook respects untouched code:** tracked files get lint errors reported only on lines
  changed since HEAD, no auto-fix, and formatting only if the file was already formatted.
  New files are formatted, fixed and linted in full.
- **Hooks work on Windows:** rewritten in Node (TypeScript stack) and Python (Python stack); the old
  bash hooks needed `jq`, which Git Bash lacks, and silently did nothing without it.
- `.ai-session/` (local AI working state) is git-ignored and skipped by ESLint, Prettier, Ruff and
  the hooks.
- `init-project` offers the commit instead of committing.

Rules:

- **PY-5 [tool]** (stack: python) `open()` needs an explicit encoding (Ruff `PLW1514`); no mutable
  default arguments (`B006`). **BREAKING** for Python code that opens files without an encoding.

## 0.2.0

- `CLAUDE.md` is now project-owned: created once, never overwritten (`_skip_if_exists`), no longer
  blocked by the managed-files hook. A Copier task guarantees only the `@AGENTS.md` import line.
- Claude Code instructions moved from `CLAUDE.md` into an "## Claude Code" section of `AGENTS.md`.
- New `scripts/adopt.py`: safe merge into existing projects (never overwrites; JSON key merge,
  `.gitignore` line merge, `<file>.ai-standards` for review). Never adds `package.json` `"type"`.
- `init-project` adopt mode uses `adopt.py` instead of `copier copy` (which aborts on conflicts or,
  with `--overwrite`, replaces user files).
- Default template source: `gh:Mustafa212/ai-standards`.
- Projects on 0.1.0: your `CLAUDE.md` is left as it is on update. You can delete its old
  "Claude Code specifics" section, which now lives in `AGENTS.md`.

## 0.1.0

- Initial layers: base rules, TypeScript and Python stacks, orgs `personal` and `example-corp`.
- `[tool]` enforcement: ESLint (strict type-checked) + Prettier, Ruff + mypy strict, coverage
  thresholds, pre-commit (gitleaks, Conventional Commits), CI.
- Claude Code hooks: lint every edited file, block edits to managed files.
- Plugin: `init-project`, `update-standards`, `propose-rule` skills and a SessionStart hook.
- Rule regression tests in `tests/violations/`.
