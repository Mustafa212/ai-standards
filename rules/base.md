{% import "config/settings.jinja" as cfg with context -%}
Every rule has an ID and an enforcement level:

- **[tool]** enforced by formatter / linter / type checker / CI. Breaking it blocks the merge. Never disable it to get green.
- **[review]** checked in code review (human or AI reviewer).
- **[ai]** guidance on how to work.

## 0. Definition of done

- **DONE-1 [tool]** Run `{{ cfg.check_cmd }}` and make it pass before saying a task is done. Report the real result; never claim success without running it.
- **DONE-2 [review]** Every behaviour change ships with tests that would fail without it.
- **DONE-3 [ai]** Keep changes small and focused, one concern per change. If a task grows, stop and propose splitting it.

## 1. Readability first

- **RDB-7 [review]** Write code a new teammate understands on first read: plain steps over clever one-liners, one idea per line. If code needs a comment to say what it does, simplify the code first.
- **RDB-1 [tool]** {% if stack == "typescript" %}Functions ≤ {{ cfg.max_function_lines }} lines{% else %}Functions ≤ {{ cfg.max_statements }} statements{% endif %}, cyclomatic complexity ≤ {{ cfg.max_complexity }}, ≤ {{ cfg.max_params }} parameters (use an options object beyond that), nesting depth ≤ {{ cfg.max_depth }}. Use early returns and guard clauses.
- **RDB-2 [tool]** Files ≤ {{ cfg.max_file_lines }} lines. A file past that has more than one responsibility.
- **RDB-3 [review]** Names say what, not how: `unpaidInvoices` not `list2`, `isExpired` for booleans, verbs for functions. No abbreviations except universal ones (id, url, http).
- **RDB-4 [tool]** No magic numbers. Name them as constants.
- **RDB-5 [review]** Comments explain *why*, not *what*. Delete commented-out code; git remembers.
- **RDB-6 [tool]** Formatting is automatic. Never hand-format.
- **RDB-8 [tool]** Every exported function and class starts with a doc comment ({% if stack == "typescript" %}JSDoc `/** … */`{% else %}a docstring{% endif %}) saying what it is for and anything a caller must know. One sentence is enough; tests are exempt.
- **RDB-9 [review]** Names a reader understands: single letters only for short loop counters. No boolean flag arguments (`send(user, true)`): use an options object or two functions.

## 2. Before writing code

- **READ-1 [ai]** Search the codebase for an existing function, type or pattern before writing a new one. Duplicating an existing utility is a defect.
- **READ-2 [ai]** Follow the patterns already used in the module you are touching.
- **READ-3 [ai]** If requirements are ambiguous, ask instead of guessing. State any assumptions you made.
- **READ-4 [review]** No new dependency without a one-line justification (why, alternatives, maintenance status).

## 3. Design

- **DES-1 [review]** One responsibility per function and module. Keep pure logic separate from I/O (network, DB, filesystem, clock) so it is testable.
- **DES-2 [review]** Inject dependencies at boundaries instead of reaching for globals deep inside logic.
- **DES-3 [review]** Make illegal states unrepresentable: precise types over boolean flags and bags of optional fields.
- **DES-4 [ai]** YAGNI. No abstractions for hypothetical futures; wait for three real cases before extracting.

## 4. Errors and security

- **ERR-1 [tool]** Never swallow errors: no empty catch/except, no bare `except`.
- **ERR-2 [review]** Validate external input (requests, files, env vars) once, at the edge, and fail fast with a clear message.
- **ERR-3 [tool]** No secrets in code or git history (gitleaks runs in pre-commit and CI). Configuration comes from environment variables.
- **ERR-4 [review]** Never log secrets, tokens or personal data.

## 5. Tests

- **TST-1 [tool]** Coverage ≥ {{ cfg.coverage_target }}%. CI fails below it{% if cfg.ratcheting %} (this project: ≥ {{ cfg.coverage }}% today, see Adoption status){% endif %}.
- **TST-2 [review]** Test behaviour, not implementation. Name tests as sentences describing the behaviour.
- **TST-3 [ai]** When fixing a bug, first write a test that reproduces it.

## 6. Git

- **GIT-1 [tool]** Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **GIT-2 [tool]** pre-commit hooks stay installed. Never commit with `--no-verify`.

## 7. Suppressing and changing rules

- **SUP-1 [tool]** Every lint suppression names the exact rule and gives a reason. Blanket suppressions are rejected.
- **SUP-2 [ai]** Never weaken configs (lint, type checker, coverage, CI, these instruction files) to make checks pass. Fix the code. If a rule is wrong, propose a change upstream.
- **EVO-1 [ai]** If the same review comment or mistake shows up twice, propose a new rule upstream, ideally one a tool can enforce.
