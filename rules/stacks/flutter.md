## Stack: Flutter (Dart)

- **DART-1 [tool]** The strict analyzer (`very_good_analysis`) passes with no infos; types are explicit where not obvious, and nothing calls through `dynamic`.
- **DART-2 [tool]** Futures are awaited or wrapped in `unawaited()`, and nothing uses `print` (use a logger).
- **DART-3 [tool]** `const` constructors wherever possible, and `context.mounted` is checked after an `await`.
- **DART-4 [tool]** Enum switches are exhaustive, with no `default`.
- **DART-5 [review]** MVVM layers, as in the Flutter architecture guide: views (widgets) hold no logic, view models hold UI state, repositories (abstract classes) own data, and services wrap platforms and APIs. Data flows one way. Folders follow the guide's layout: `lib/ui/<feature>/` holds that feature's view model and widgets, `lib/ui/core/` the widgets and themes views share, `lib/data/repositories/` and `lib/data/services/` the data layer, `lib/domain/models/` the app's data types, and `test/` mirrors `lib/`.
- **DART-6 [review]** Data models are immutable (`freezed` or a hand-written `copyWith`).
- **DART-7 [review]** Dependencies are injected (constructor parameters, with provider, Riverpod or get_it at the edge); no global singletons.
- **DART-8 [review]** A big `build` method is split into small widget classes, not helper methods.
- **DART-9 [review]** Every async screen shows loading, error and empty states; text is localized, and layouts are RTL-safe (`EdgeInsetsDirectional`).
- **DART-10 [review]** Each layer is tested on its own and together: fakes over mocks, and widget tests for key screens.

RDB-1 (size, complexity, parameters, nesting) and RDB-4 (magic numbers) have no free Dart analyzer
rule, so in Flutter they are checked in review. RDB-2 (file length) is checked by `check.sh`.

| Task | Command |
| --- | --- |
| Everything CI runs | `bash .ai-standards/check.sh` |
| Format | `dart format lib test` |
| Tests | `flutter test` |
| Add the platform folders (android, ios, web…) | `flutter create . --project-name <package>` |
