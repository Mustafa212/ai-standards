# Changelog

Versions follow semver, from the point of view of a project that runs `copier update`:

- **MAJOR**: existing, previously-passing code may now fail checks (stricter threshold, new
  `[tool]` rule that errors). Projects should plan time for the update.
- **MINOR**: new `[review]`/`[ai]` rules, new orgs, stacks or tooling that does not fail existing code.
- **PATCH**: wording, docs, bug fixes in templates.

Each entry names the rule ID, the layer (base / stack / org) and the enforcement level.

## 0.16.0 — 2026-10-18

**BREAKING** (adopted typescript, angular and python projects, and any project's audit): two
[tool] checks get stricter, so `copier update` can bring new lint findings. Fix them, or baseline
them as with any new rule (ADOPT-2). Agents had been dumping files into one folder, skipping
comments and writing clever code; the rules covered part of it, and published guidance covers the
rest.

- **RDB-11 [review]** (base, new) Folders by feature, not by kind: what a feature needs lives in its
  folder, shared code in a folder named for its job (RDB-10), and a folder past about 15 files or 4
  levels deep is split; feature folders sit inside the stack's architecture layers. Sources:
  angular.dev style guide ("Avoid putting so many files into one directory…"), Microsoft's "Feature
  Slices for ASP.NET Core MVC" ("perhaps five to 15 items"), NestJS feature modules, bulletproof-react,
  the React FAQ on nesting. NG-8 now points to it for its folder half.
- **DART-5 [review]** (flutter, amended) The folder layout of Flutter's architecture case study:
  `lib/ui/<feature>/`, `lib/ui/core/`, `lib/data/repositories/` and `services/`,
  `lib/domain/models/`, and `test/` mirroring `lib/`.
- **RDB-5 [review]** (base, amended) Says when a comment is required, not only what it may not do:
  a workaround with its issue link, a business rule, a deliberate limit or trade-off, an order or
  value that looks wrong but isn't. Sources: Google Python style guide 3.8.5 ("If you're going to have
  to explain it at the next code review, you should comment it now"), Google C++ and Go guides.
- **RDB-8 [tool]** (base, amended, **BREAKING**) Public methods of exported classes need a doc comment
  too. TypeScript and Angular: `jsdoc/require-jsdoc` gets a `MethodDefinition` context (private,
  protected and `#private` members, constructors and Angular's `ngOnInit`-style hooks are exempt;
  classes that aren't exported stay exempt through `publicOnly`). Python: Ruff `D102`. .NET (CS1591)
  and Flutter (`public_member_api_docs`) already covered every public member. Sources: PEP 257,
  Google Java style 7.3, Microsoft's C# documentation conventions.
- **RDB-1 [tool]** (typescript, angular, dotnet, amended, **BREAKING**) Cognitive complexity ≤ 15
  (`max_cognitive`, an org setting), which also counts nesting and broken flow, as cyclomatic
  complexity doesn't. TypeScript and Angular: `sonarjs/cognitive-complexity` from the new dev
  dependency `eslint-plugin-sonarjs` (^4.2.1); .NET: `S3776` with its threshold in SonarLint.xml.
  Python and Flutter have no free rule for it and keep cyclomatic complexity only. Source: Sonar's
  Cognitive Complexity paper.
- **RDB-7** (dotnet): nested conditional operators fail the build (`S3358`), as `no-nested-ternary`
  already does in TypeScript.
- Violation tests prove each new check fires: `documentation.ts` (typescript, angular),
  `documentation.py`, `complexity.cs`.

## 0.15.0 — 2026-10-18

MINOR: fix-debt ordering and shorter skill descriptions; no rule text changes.

- **Debt where the code changes first (fix-debt):** `fix_debt.py items --project <project>` orders
  each priority by the commits in the last 90 days that touched the item's folder, then by count, and
  shows that number in the round's table. Debt in a module edited every week is copied into every new
  change (READ-2), while debt in a folder nobody touches can wait.
- **Shorter skill descriptions:** the five longest now hold only their triggers, their promises
  (read-only, nothing in the project changes, writes and commits) and the "use X instead" lines, 39%
  shorter, since descriptions load into every session. A trigger eval (`claude plugin eval`, one case
  per skill and two that must trigger none) passed for every skill on sonnet. `init-project` didn't
  fire on the old wording (0 of 2) and now says to run it before any file is written or any
  scaffolding command runs (2 of 3).

## 0.14.0 — 2026-10-18

MINOR: audit, onboard and fix-debt fixes; no rule text changes.

- **Auditor groups are data (audit):** `config/rule-groups.json` names each base, stack and
  architecture rule's auditor group, and `scripts/check_rules.py` fails on a rule (other than `[ai]`)
  in no group or in two, and on a group entry for a rule that doesn't exist. The list written into
  the audit skill had fallen behind: CS-18 (authorization fallback) and NG-12 (tokens in browser
  storage) went to the catch-all group instead of the security auditor. A new group, "Data and
  persistence", takes the EF Core rules (CS-15 to CS-17, CS-19 to CS-23).
- **Declined proposals stay declined (onboard):** a row dropped for a lasting reason leaves
  `<!-- declined: <proposal> <date>: <reason> -->` in the project file, and later rounds and refresh
  mode don't propose it again.
- **Skipped false positives stay skipped (fix-debt):** `fix_debt.py skip <out> --item <id> --reason`
  records one in `skipped.json`; `items` leaves it out until its count grows past the count it was
  skipped at.
- **Rule text beside IDs:** the fix-debt items table, the onboard move-up question and the audit's
  top 3 give each rule's short text, so an approval isn't made from bare IDs.
- **propose-rule:** a new rule also goes into `config/rule-groups.json` (and, when the prefix
  default doesn't fit, `config/rule-priority.json`).

## 0.13.0 — 2026-10-17

MINOR: three new `[review]` rules for API stacks (typescript, python, dotnet); nothing fails existing code.
An audit run after updating can report new findings for them.

- **DES-10 [review]** (base, P1) A collection that can grow is paged from its endpoint's first release, with a server-capped page size and an opaque cursor or next link left out on the last page. Sources: Google AIP-158, Microsoft Azure REST API guidelines, Zalando #160, OWASP API4:2023.
- **ERR-10 [review]** (base, P1) Accepting an upload: size caps, an extension allow-list checked against the magic bytes, a generated storage name outside the web root, the user's file name kept as encoded display metadata. Sources: ASP.NET Core file-upload docs, OWASP File Upload cheat sheet, OWASP ASVS 5.0 5.2.1, 5.2.2, 5.3.2.
- **ERR-11 [review]** (base, P1) Serving an upload to other users: after a malware scan, through the owning record's access check (ERR-7), with the encoded file name in `Content-Disposition`. Sources: ASP.NET Core file-upload docs, OWASP File Upload cheat sheet, OWASP ASVS 5.0 5.4.1-5.4.3.

## 0.12.1 — 2026-10-17

PATCH: skill text and one priority; no rule text changes and nothing new in a rendered project.
Lessons from the first real onboard, audit and fix-debt run on an AI-written monorepo.

- **onboard, consistency isn't correctness:** code written mostly by an AI is consistent by habit.
  A proposed Rule or Exception candidate now names its **Source** (official docs, a large company's
  published standard, an RFC, OWASP). A consistent pattern the guides contradict is a Wrong
  pattern, so its places are findings to fix. The table has a Source column.
- **fix-debt, .NET on Microsoft.Testing.Platform** (`global.json` sets
  `"test": {"runner": "Microsoft.Testing.Platform"}`, as the template does):
  `cd <folder with global.json> && dotnet test --solution <sln> --report-xunit-trx --results-directory {dir}`.
  `--logger trx` is VSTest-only, and from another folder `dotnet test` falls back to VSTest and
  rejects `--solution`.
- **fix-debt, behavior is judged per item:** an item whose fix changes a response, a status code
  or stored data goes with the P1 items, whatever its priority.
- **ERR-5 is P3:** a message that doesn't say what to do next was P1 only because every ERR rule
  defaulted to P1.

## 0.12.0 — 2026-10-17

**BREAKING** (minor bump while 0.x): two new `[tool]` rules can fail existing code. CS-24 bans
reading the clock directly in .NET production code, and NG-11 bans bypassing Angular's sanitizer.
Every other change is `[review]`. Each rule comes from published guidance: OWASP (the API Top 10
and its cheat sheets), Microsoft Learn (ASP.NET Core authorization, EF Core, TimeProvider), RFC
3339, angular.dev security, Zalando's API guidelines and Martin Fowler's Money pattern.

- **Base, [review]:**
  - **DES-8 (P1, server stacks only):** a database constraint, not only a check-then-insert;
  - **DES-9 (P2):** moments in UTC with an offset, calendar dates without a time, and the business
    date from one time-zone helper;
  - **ERR-6 (P1):** no binary floating point for money;
  - **ERR-7, ERR-8, ERR-9 (P1, server stacks only):** object-level authorization, the server
    re-derives prices and roles, and no internals in error responses.
- **dotnet:**
  - **CS-10** now also forbids binding requests to entities (over-posting);
  - **CS-12** no longer names tests (`Method_Scenario_Expected` contradicted base TST-2, which asks
    for behavior sentences), and requires a real database instead of an in-memory provider;
  - **[review]:**
    - **CS-18 (P1):** a fallback policy, and policies instead of roles on endpoints;
    - **CS-19 (P1):** decimal precision;
    - **CS-20 (P1):** a concurrency token and a 409;
    - **CS-21 (P1):** one `SaveChangesAsync` per use case;
    - **CS-22 (P2):** a `HasPendingModelChanges` test;
    - **CS-23 (P1):** read every migration;
    - **CS-25 (P4):** `is null` patterns;
  - **CS-24 [tool] (P2):** `DateTime.Now`, `UtcNow` and `Today`, and `DateTimeOffset.Now` and
    `UtcNow`, are banned through RS0030 for every org. The org's own bans follow them in
    `BannedSymbols.txt`.
- **angular:**
  - **NG-11 [tool] (P1):** `no-restricted-properties` bans `bypassSecurityTrust*`, `innerHTML`,
    `outerHTML`, `insertAdjacentHTML` and `document.write` (off in spec files, which read the rendered
    HTML); a vetted bypass takes a SUP-1 suppression;
  - **NG-12 [review] (P1):** no tokens or personal data in web storage.
- **Audit:** a tool message that names its rule (`… (CS-24).`) is counted under that rule, because
  one tool ID such as RS0030 can serve a stack rule and an org rule.
- **Break shapes** for every new `[review]` rule; violation tests for CS-24 and NG-11.
- **Checked against the sources:** each new or amended rule was compared with the guide it cites,
  and the wording was tightened where it overstated or missed a case: 8 rules held as written,
  21 were reworded, and none was contradicted.
## 0.11.1 — 2026-10-17

PATCH: a bug fix in the audit script; no rule text changes and nothing new in a rendered project.

- **dotnet audit with the solution in a subfolder** (for example `backend/` next to `frontend/`).
  The audit's props and targets were written at the repo root, and MSBuild never reads them when
  the solution's folder has a `Directory.Build.props` of its own. The analyzers didn't run, and the
  report said `ran` with 0 findings. They now go next to the solution. When that folder has no props
  of its own, they import the ones above, as MSBuild would. A build that writes no analyzer results
  is `failed`, never clean. Found on the first real audit of a monorepo (0 findings before the fix,
  5,730 after). fix-debt's `verify` uses the same runner, so it is fixed too.
- **New tests:** the overlay next to a solution in a subfolder; the import from above; no SARIF
  means failed; and one that evaluates the overlay with real MSBuild when dotnet is installed
  (skipped otherwise).

## 0.11.0 — 2026-10-16

MINOR: new plugin behavior; nothing that fails existing code.

- **fix-debt in rounds, for every stack** (part 2 of 3). You approve a round of up to 10 items once
  (P1 items one by one). Each item gets one commit, and the round ends in one pull request. Per
  item:
  - a clean test run, then a canary: one deliberate break must turn a test red;
  - characterization tests pinned first when no test sees the code;
  - the fix, an after run, and the analyzer re-run showing the item gone with nothing new;
  - a verdict computed by `scripts/fix_debt.py` from the runners' own result files (TRX, JUnit,
    jest JSON, flutter JSON, or a summary line), never from the agent's account;
  - every run tied to the commit it ran on: a stale or uncommitted run, a canary that only broke
    the build, a suppression or a changed analyzer setting stops the item;
  - senior-dev's blind reviewer when it's installed.

  Why: the proof method of Anthropic's code-modernization plugin, re-implemented in our scripts
  for in-place debt fixes with analyzer proof.
- **New scripts:** `scripts/fix_debt.py` and `scripts/run_results.py` (standard library only).

## 0.10.0 — 2026-10-16

MINOR: new [review] rules and a removed [ai] rule; nothing that fails existing code.

- **CS-10 split (stack dotnet, [review]):** CS-10 bundled four checks, so an audit count mixed
  defects with different fixes. Now one idea each: CS-10 never return EF Core entities from an
  API (map to DTOs); **CS-15** filter, page and project in the database; **CS-16** no N+1
  queries; **CS-17** reads that don't update use `AsNoTracking()`. CS-15 and CS-16 keep CS-10's
  P1 priority; CS-17 is P3. A project exception that targeted CS-10 now covers only the
  entities-over-the-API part: re-check it.
- **Breaking a rule (base, intro):** when a task can't be done without breaking a [tool] or
  [review] rule, the agent stops and asks; the outcome is a fix or an approved project exception,
  never a silent break. Going against an [ai] rule is said, with the reason.
- **TST-3 removed (base, [ai]):** "first write a test that reproduces the bug" is covered by
  DONE-2 [review] (every behaviour change ships with a test that fails without it). Its ID stays
  retired (`<!-- removed: … -->`). The other [ai] rules stay: AGENTS.md is also read by Cursor,
  Copilot and other agents, so "Claude does it anyway" doesn't hold for them.

## 0.9.2 — 2026-10-16

PATCH: plugin skill text and script checks only; no rule text changes and nothing new in a rendered
project. Taken from a comparison with similar standards and skill plugins (ideas only, in our own
words).

- **onboard:** a row's evidence is the search, 2–3 `file:line` hits and the places that differ;
  cited lines are reopened before the table is shown, and the rows they don't support are dropped
  (with a count). Comment-only patterns aren't rules. At most 10 rows per round, highest count
  first. Decisions are asked per row with AskUserQuestion (up to 4 per call); a typed answer is
  saved in the user's words, a yes to the whole table isn't a decision, and without the tool nothing
  is saved. A deleted project rule leaves `<!-- removed: <ID> <date>: <reason> -->`, which counts
  when choosing the next ID. The private-copy and new-org setup moved to `references/setup.md`, and
  the old step 8 (general rules go to the public repo) is now part of step 6.
- **Break shapes for `[review]` rules:** new `rules/examples/<rule file>.md` (org and project rules:
  `orgs/<org>/examples.md`), with a search and a bad snippet per rule ID. The template never renders
  them into AGENTS.md. propose-rule saves them, the audit puts them in the auditor brief, and
  `rule-auditor` starts from them. Seeded for RDB-5, RDB-9, RDB-10, TST-4, ERR-4 (base), CS-8, CS-14
  (dotnet), CLEAN-2 (dotnet clean), TS-5 (typescript), NG-7, NG-9, NG-10 (angular), PY-3 (python),
  DART-7 and DART-8 (flutter).
- **`check_rules.py`:** rejects an ID that a `removed:` or `moved to org:` marker retired, and a
  break shape for a rule that doesn't exist.
- **audit:** before writing `review.json`, the first example of each high-confidence finding is
  reopened. A rule whose examples don't hold moves to `not_checked`, and the summary says how many
  were dropped. The summary starts with what wasn't checked, which is unchecked, not clean.
- **fix-debt:** code with no test gets a test of today's behavior first; a P1 fix shows its new
  test failing before the fix; the test runner's run/failed/skipped line is reported before and
  after, and zero tests run isn't a pass.
- **SessionStart:** the empty-folder message is calmer (no "REQUIRED… MUST"); it still points to
  `ai-standards:onboard`.
- **Shorter skills:** the Python and copier runner notes are in one shared
  `plugin/references/runners.md`, and adopt-project's stack notes are in `references/stacks.md`.

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
