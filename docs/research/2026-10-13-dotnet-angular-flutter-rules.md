# Clean-code rules for .NET, Angular and Flutter: research and proposal

Date: 2026-10-13, claims re-checked against the sources on 2026-10-14 · Status: **approved by the owner on 2026-10-14.**
Base rules (section 3) are applied in 0.5.0. The .NET, Angular and Flutter stacks follow as their own releases.

## 1. Who we learned from, and why

| Source | Why it counts |
| --- | --- |
| [.NET runtime C# coding style](https://github.com/dotnet/runtime/blob/main/docs/coding-guidelines/coding-style.md) | The style of .NET itself; Microsoft's docs and samples adopted it. |
| [C# coding conventions](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/coding-conventions) (Microsoft Learn, 2025) | The conventions behind every official sample. |
| [.NET code analysis](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/overview) | How to make the compiler enforce quality and style (`AnalysisLevel`, `EnforceCodeStyleInBuild`). |
| [Clean Architecture template](https://github.com/jasontaylordev/CleanArchitecture) (~20k stars) | One of the most starred .NET solution templates: layers, ADRs, tests with a real database. |
| [Angular style guide](https://angular.dev/style-guide) (Angular v22) | The Angular team's own guide, updated for signals and `inject()`. |
| [angular-eslint](https://github.com/angular-eslint/angular-eslint) | The lint rules that turn that guide into checks. |
| [Flutter architecture recommendations](https://docs.flutter.dev/app-architecture/recommendations) | The Flutter team's guidance, rated *strongly recommend*, *recommend* or *conditional*. |
| [Flutter repo style guide](https://github.com/flutter/flutter/blob/master/docs/contributing/Style-guide-for-Flutter-repo.md) | How the Flutter framework itself is written; its first principle is "optimize for readability". |
| [Effective Dart](https://dart.dev/effective-dart) | The Dart team's style, docs, usage and design guide. |
| [very_good_analysis](https://pub.dev/packages/very_good_analysis) (Very Good Ventures, v11) | One of the strictest widely used Dart lint sets, from one of the best-known Flutter consultancies. |

The sources agree on a short list of ideas: **code is read far more than it is written**; the UI only
shows state while logic lives below it; data is immutable; dependencies are injected; errors are
specific and say what to do; the compiler or linter enforces anything it can.

## 2. Where each kind of rule belongs

| Layer | What goes there | Example |
| --- | --- | --- |
| **base** | True in every language, worth checking in every review | "the UI shows state, it holds no business logic" |
| **stack** | True for every project in that language or framework, ideally tool-enforced | `Nullable` on and warnings as errors (.NET) |
| **org** | A *choice* a team makes once for all its projects | Clean Architecture or vertical slices; Bloc or Riverpod; Nx boundaries |
| **project** | One project's own facts | "money goes through `Money`", "API clients live in `infrastructure/http`" |

Rule of thumb: if two reasonable teams would choose differently, it's **org**, not stack.

## 3. Proposed base rules (all stacks)

Base already covers most of the sources (RDB, DES, ERR, TST). These are the gaps:

| ID | Level | Rule | Seen in |
| --- | --- | --- | --- |
| DES-5 | review | **Data is immutable by default**: records, `readonly`, `final`, frozen dataclasses. Change data by making a new value. | Flutter (strongly recommend), C# records, PY-3 |
| DES-6 | review | **The UI shows state and forwards events; business logic lives below it** (view models, services, handlers). | Flutter "no logic in widgets", Angular "components focus on presentation", CS-API-01 |
| DES-7 | tool where possible | **Switches over an enum or union handle every case, with no catch-all default**, so a new value fails the build. | Flutter style guide, TS-2 |
| RDB-10 | review | **A file is named after what it holds.** No dumping-ground names such as `utils`, `helpers` or `common`: name it for its job (`date-format`, `tax`). | Angular style guide ("Avoid generic file names such as `helpers.ts`, `utils.ts`, and `common.ts`") |
| ERR-5 | review | **Error messages say what happened and what to do next.** | Flutter repo style guide |
| TST-4 | review | **Tests never rely on timing** (no sleeps or timeouts): wait for the event. Prefer fakes to mocks. | Flutter repo style guide, Flutter architecture |

"One concept per file" is **not** a base rule, because the sources disagree. Angular's guide asks
for it, and in C# one public type per file named after it is the common convention (StyleCop
`SA1402`, `SA1649`). The Flutter repo prefers the opposite: Dart's private classes are visible only
inside their file, so it keeps a widget's small private helpers in the same file rather than making
them public just to split them. It goes to the Angular and .NET stacks instead (NG-8, CS-2).

RDB-8 (doc comments on exported code) already maps cleanly to every stack: C# `CS1591` with
`GenerateDocumentationFile`, Dart `public_member_api_docs`, ESLint `jsdoc/require-jsdoc`, Ruff `D101`/`D103`.

## 4. Stack: .NET (C#)

**Tooling, all enforced in `Directory.Build.props` and CI:**
`<Nullable>enable</Nullable>`, `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`,
`<AnalysisLevel>latest-Recommended</AnalysisLevel>`, `<EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>`,
`<GenerateDocumentationFile>true</GenerateDocumentationFile>`, an `.editorconfig` based on the runtime's
style, and `dotnet format --verify-no-changes` in CI. Rules outside the `Recommended` set (CA1031,
CA1852, CA1507) are raised to `warning` in `.editorconfig`. Coverage with coverlet and a threshold
(TST-1).

| ID | Level | Rule | Enforced by |
| --- | --- | --- | --- |
| CS-1 | tool | Nullable reference types on; every warning is an error. | `Nullable`, `TreatWarningsAsErrors` |
| CS-2 | tool | File-scoped namespaces, `using` outside the namespace, `System.*` first, explicit access modifiers, `_camelCase` private fields, keywords over BCL names (`int`, not `Int32`). One public type per file, named after it. | `.editorconfig` IDE0161, IDE0065, IDE0040, IDE1006, IDE0049; StyleCop SA1402, SA1649 |
| CS-3 | tool | `var` only when the type is obvious from the right side (`new`, a cast, a literal). | IDE0007/IDE0008 options |
| CS-4 | tool | Catch only what you can handle (no bare `catch (Exception)` without a filter), rethrow with `throw;`. | CA1031, CA2200 |
| CS-5 | tool | Pass `CancellationToken` through every async I/O call. | CA2016 |
| CS-6 | tool | Seal internal and private types, and make members `static` when they use no instance state. | CA1852, CA1822 |
| CS-7 | tool | `nameof(x)` instead of string literals for member names. | CA1507 |
| CS-8 | review | Async all the way: no `.Result`, `.Wait()` or `async void` (except event handlers). | senior-dev CS-ASYNC-01/02 |
| CS-9 | review | Data types are records, or classes with `required` and `init` properties. | C# conventions, DES-5 |
| CS-10 | review | Never expose EF entities from an API; filter, page and project in the database; no N+1 queries; `AsNoTracking` for reads. | senior-dev CS-DTO-01, CS-EF-01..03 |
| CS-11 | review | Respect DI lifetimes (no scoped service inside a singleton); read settings through `IOptions<T>`. | senior-dev CS-DI-01, CS-CONF-01 |
| CS-12 | review | Tests are named `Method_Scenario_Expected` and test behavior against a real database where data matters (Testcontainers or Respawn). | senior-dev CS-TEST-01, Clean Architecture template |

**Org choices (not stack):** Clean Architecture or vertical slices, enforced by architecture tests
(NetArchTest or ArchUnitNET) so the dependency direction can't break; MediatR/CQRS or plain
services; manual mapping or a generator such as Mapperly (AutoMapper and MediatR now ship under a
[commercial dual license](https://www.jimmybogard.com/automapper-and-mediatr-commercial-editions-launch-today/),
so that decision is an org's); result types or exceptions for expected failures;
extra analyzers (StyleCop, SonarAnalyzer, Meziantou).

**Not proposed:** StyleCop's full set at stack level (it demands comments on private members, which
is noise against RDB-5); a 65-character line limit (written for docs pages, not for code).

## 5. Stack: Angular (built on the TypeScript stack: TS-1..TS-6 and RDB-8 still apply)

**Tooling:** `angular-eslint` (recommended + template recommended), Angular's `strict` options
(`strictTemplates`, `strictInjectionParameters`), Prettier, Vitest (Angular's
[default runner since v21](https://angularindepth.com/article/ng-news-25-43-vitest-angulars-new-testing-framework/)).

| ID | Level | Rule | Enforced by |
| --- | --- | --- | --- |
| NG-1 | tool | Standalone components with `OnPush` change detection. | `prefer-standalone`, `prefer-on-push-component-change-detection` |
| NG-2 | tool | Dependencies come from `inject()`, declared at the top of the class. | `prefer-inject`, `inject-at-top` |
| NG-3 | tool | State is signals (`signal`, `computed`, `input()`, `output()`), not decorators and setters. | `prefer-signals` |
| NG-4 | tool | Templates use `@if`/`@for`/`@switch`; `@for` always has `track`. | template `prefer-control-flow` (recommended since angular-eslint 21), the compiler |
| NG-5 | review | Components only present. Validation, transformation and data access live in services or plain functions; complex template logic becomes a `computed`. | Angular style guide, DES-6 |
| NG-6 | review | Members used only by the template are `protected`; inputs, outputs, models and queries are `readonly`. | Angular style guide |
| NG-7 | review | Event handlers are named for what they do (`saveDraft()`), not the event (`onClick()`). | Angular style guide |
| NG-8 | review | One concept per file (a component, a directive or a service), named in kebab-case after it. Folders by feature, not by type (no `components/`, `services/`); specs next to the code. | Angular style guide, RDB-10 |
| NG-9 | review | `class`/`style` bindings instead of `NgClass`/`NgStyle`; lifecycle hooks stay short and call well-named methods. | Angular style guide |
| NG-10 | review | Long-lived subscriptions end with the component (`takeUntilDestroyed`, `async` pipe, `toSignal`); one-shot HTTP calls need nothing. | senior-dev NG-RX-01 |

**Org choices:** an Nx monorepo with `@nx/enforce-module-boundaries`; NgRx SignalStore or services
with signals; the UI library; the i18n mechanism and RTL support.

## 6. Stack: Flutter (Dart)

**Tooling:** `very_good_analysis` (or `flutter_lints` plus `strict-casts`, `strict-inference`,
`strict-raw-types`), `flutter analyze --fatal-infos` and `dart format --set-exit-if-changed` in CI,
coverage with a threshold.

| ID | Level | Rule | Enforced by |
| --- | --- | --- | --- |
| DART-1 | tool | The strict analyzer passes with no infos; types are explicit where not obvious; no `dynamic` calls. | `very_good_analysis`, `avoid_dynamic_calls` |
| DART-2 | tool | Futures are awaited or wrapped in `unawaited()`; no `print` (use a logger). | `unawaited_futures`, `discarded_futures`, `avoid_print` |
| DART-3 | tool | `const` constructors wherever possible; check `context.mounted` after an `await`. | `prefer_const_constructors`, `use_build_context_synchronously` |
| DART-4 | tool | Enum switches are exhaustive with no `default`. | `exhaustive_cases`, `no_default_cases` |
| DART-5 | review | MVVM layers: views (widgets) hold no logic, view models hold UI state, repositories (abstract classes) own data, services wrap platforms and APIs. Data flows one way. | Flutter architecture (strongly recommend) |
| DART-6 | review | Data models are immutable (`freezed` or hand-written `copyWith`). | Flutter architecture (strongly recommend), DES-5 |
| DART-7 | review | Dependencies are injected (provider, Riverpod or get_it at the edge); no global singletons. | Flutter architecture, Flutter repo "avoid secret state" |
| DART-8 | review | Split big `build` methods into small widget classes, not helper methods. | senior-dev DART-WIDGET-01 |
| DART-9 | review | Every async screen shows loading, error and empty states; text is localized and layouts are RTL-safe (`EdgeInsetsDirectional`). | senior-dev DART-UI-01..03 |
| DART-10 | review | Each layer is tested on its own and together; fakes over mocks; widget tests for key screens. | Flutter architecture (strongly recommend) |

**Org choices:** the state management (Bloc, Riverpod, or ChangeNotifier with Commands as in the
Flutter guide); `go_router` for navigation; golden tests; very high coverage targets (Very Good
Ventures [aims for 100%](https://verygood.ventures/blog/very-good-coverage), enforced with
`very_good test --coverage --min-coverage 100`).

## 7. How this reaches the template (a later feature, after approval)

Each stack needs what TypeScript and Python have today: template files, lint and format config, a
`check` command, Claude hooks, CI, `tests/violations/` for every `[tool]` rule, and a passing fresh
scaffold. Angular would build on the TypeScript stack rather than copy it. Suggested order: **.NET
first** (the main work projects), then Angular, then Flutter.

## 8. Decisions needed from the owner

1. Approve, change or drop each base rule in section 3.
2. Approve the stack tables (sections 4–6), and confirm which items are org choices.
3. Confirm the order: .NET, then Angular, then Flutter.
