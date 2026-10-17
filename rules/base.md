{% import "config/settings.jinja" as cfg with context -%}
Every rule has an ID and an enforcement level:

- **[tool]** enforced by formatter / linter / type checker / CI. Breaking it blocks the merge. Never disable it to get green.
- **[review]** checked in code review (human or AI reviewer).
- **[ai]** guidance on how to work.

When a task can't be done without breaking a [tool] or [review] rule, stop and ask: the outcome is
a fix, or a project exception the user approves, never a silent break. When you go against an [ai]
rule, say so and why.

## 0. Definition of done

- **DONE-1 [tool]** Run `{{ cfg.check_cmd }}` and make it pass before saying a task is done. Report the real result; never claim success without running it.
- **DONE-2 [review]** Every behaviour change ships with tests that would fail without it.
- **DONE-3 [ai]** Keep changes small and focused, one concern per change. If a task grows, stop and propose splitting it.

## 1. Readability first

- **RDB-7 [review]** Write code a new teammate understands on first read: plain steps over clever one-liners, one idea per line. If code needs a comment to say what it does, simplify the code first.
- **RDB-1 {% if stack == "flutter" %}[review]{% else %}[tool]{% endif %}** {% if stack == "python" %}Functions ≤ {{ cfg.max_statements }} statements{% else %}Functions ≤ {{ cfg.max_function_lines }} lines{% endif %}, cyclomatic complexity ≤ {{ cfg.max_complexity }}, ≤ {{ cfg.max_params }} parameters (use an options object beyond that), nesting depth ≤ {{ cfg.max_depth }}. Use early returns and guard clauses.
- **RDB-2 [tool]** Files ≤ {{ cfg.max_file_lines }} lines. A file past that has more than one responsibility.
- **RDB-3 [review]** Names say what, not how: `unpaidInvoices` not `list2`, `isExpired` for booleans, verbs for functions. No abbreviations except universal ones (id, url, http).
- **RDB-4 {% if stack == "flutter" %}[review]{% else %}[tool]{% endif %}** No magic numbers. Name them as constants.
- **RDB-5 [review]** Comments explain *why*, not *what*. Delete commented-out code; git remembers.
- **RDB-6 [tool]** Formatting is automatic. Never hand-format.
- **RDB-8 [tool]** Every exported function and class starts with a doc comment ({% if stack in ["typescript", "angular"] %}JSDoc `/** … */`{% elif stack == "dotnet" %}an XML doc comment, `/// <summary>`{% elif stack == "flutter" %}a dartdoc comment, `///`{% else %}a docstring{% endif %}) saying what it is for and anything a caller must know. One sentence is enough; tests are exempt.
- **RDB-9 [review]** Names a reader understands: single letters only for short loop counters. No boolean flag arguments (`send(user, true)`): use an options object or two functions.
- **RDB-10 [review]** A file is named after what it holds. No dumping-ground names such as `utils`, `helpers` or `common`: name it for its job (`date-format`, `tax`).

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
- **DES-5 [review]** Data is immutable by default ({% if stack in ["typescript", "angular"] %}`readonly`, `as const`{% elif stack == "dotnet" %}records, `init`, `readonly`{% elif stack == "flutter" %}`final` fields, `copyWith`{% else %}frozen dataclasses, tuples{% endif %}). Change data by making a new value.
- **DES-6 [review]** The UI shows state and forwards events; business logic lives below it (view models, services, handlers).
- **DES-7 [review]** A switch over an enum or union handles every case, with no catch-all default, so a new value fails the build{% if stack in ["typescript", "angular"] %} (TS-2 enforces it){% elif stack == "dotnet" %} (use a switch expression without a `_` arm: a missing case is build error CS8509){% elif stack == "flutter" %} (DART-4 enforces it){% else %} (end a `match` with `assert_never`){% endif %}.
- **DES-8 [review]** A rule that must hold across concurrent requests (a unique invoice number, one payment per key) is a database constraint such as a unique index, not only a check-then-insert in code: two requests can both pass the check.
- **DES-9 [review]** A moment is stored and sent in UTC with an explicit offset (RFC 3339, `2026-10-17T09:30:00Z`); a calendar date such as a due date has no time part ({% if stack == "dotnet" %}`DateOnly`{% elif stack in ["typescript", "angular"] %}a `YYYY-MM-DD` string{% elif stack == "flutter" %}year, month and day only{% else %}`datetime.date`{% endif %}). Today's business date comes from one helper that applies the business's time zone.

## 4. Errors and security

- **ERR-1 [tool]** Never swallow errors: no empty catch/except, no bare `except`.
- **ERR-2 [review]** Validate external input (requests, files, env vars) once, at the edge, and fail fast with a clear message.
- **ERR-3 [tool]** No secrets in code or git history (gitleaks runs in pre-commit and CI). Configuration comes from environment variables.
- **ERR-4 [review]** Never log secrets, tokens or personal data.
- **ERR-5 [review]** Error messages say what happened and what to do next.
- **ERR-6 [review]** Never hold money in binary floating point ({% if stack == "dotnet" %}`double`, `float`{% elif stack in ["typescript", "angular"] %}arithmetic on a `number`{% elif stack == "flutter" %}`double`{% else %}`float`{% endif %}): use {% if stack == "dotnet" %}`decimal`{% elif stack == "python" %}`Decimal`{% else %}integer minor units or a decimal type{% endif %}. Floats can't store 0.10 exactly.
{% if stack in ["typescript", "python", "dotnet"] %}
- **ERR-7 [review]** Code that reads or writes a record by ID checks that the caller may access that record (owner, tenant or role), not only that someone is signed in. Changing an ID in a URL never opens another customer's data.
- **ERR-8 [review]** Prices, totals, discounts, balances and roles sent by a client are input, not truth: look them up or recompute them on the server.
- **ERR-9 [review]** Error responses never carry stack traces, exception messages, SQL or internal type names: return a generic message with a trace ID, and log the details on the server.
{% endif %}

## 5. Tests

- **TST-1 [tool]** Coverage ≥ {{ cfg.coverage_target }}%. CI fails below it{% if cfg.ratcheting %} (this project: ≥ {{ cfg.coverage }}% today, see Adoption status){% endif %}.
- **TST-2 [review]** Test behaviour, not implementation. Name tests as sentences describing the behaviour.
<!-- removed: TST-3 2026-10-16: covered by DONE-2 (a bug fix is a behaviour change, so it ships with a test that fails without it) -->
- **TST-4 [review]** Tests never rely on timing (no sleeps or timeouts): wait for the event. Prefer fakes to mocks.

## 6. Git

- **GIT-1 [tool]** Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **GIT-2 [tool]** pre-commit hooks stay installed. Never commit with `--no-verify`.

## 7. Suppressing and changing rules

- **SUP-1 [tool]** Every lint suppression names the exact rule and gives a reason. Blanket suppressions are rejected.
- **SUP-2 [ai]** Never weaken configs (lint, type checker, coverage, CI, these instruction files) to make checks pass. Fix the code. If a rule is wrong, propose a change upstream.
- **EVO-1 [ai]** If the same review comment or mistake shows up twice, propose a new rule upstream, ideally one a tool can enforce.
