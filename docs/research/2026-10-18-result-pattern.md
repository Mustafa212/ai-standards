# Expected failures as results (CS-26)

Date: 2026-10-18 · Status: **chosen by the owner on 2026-10-18**, applied in 0.19.0.

## 1. The choice, and the guidance against it

The owner chose to return expected failures as values instead of throwing them. The sources split:

| For results | Against |
| --- | --- |
| Microsoft, [best practices for exceptions](https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions): check for a condition that "happens routinely" in code; throw when it is "truly exceptional" | Microsoft, [Framework Design Guidelines, exception throwing](https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/exception-throwing): "DO report execution failures by throwing exceptions", "DO NOT return error codes" |
| Scott Wlaschin, [against railway-oriented programming](https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/): results for expected domain errors only, exceptions for the unexpected | |

The guidelines page also says "DO NOT use exceptions for the normal flow of control, if possible",
and it is written for reusable .NET libraries (the book's subtitle), not an application's handlers.
So CS-26 keeps exceptions for the unexpected (a bug, a database outage) and makes only the expected
failures values: invalid input, a missing record, a state that forbids the action.

## 2. The library

Checked 2026-10-18 on GitHub and NuGet.

| | ErrorOr | Ardalis.Result | FluentResults |
| --- | --- | --- | --- |
| Licence | MIT | MIT | MIT |
| Latest | 2.1.1, May 2026; maintained by the [error-or](https://github.com/error-or/error-or) org since April 2026 | 10.1.0, Oct 2024 | 4.0.0, Jun 2025 |
| net10.0 build | yes | through compatibility | through compatibility |
| Error model | `Error` struct: `Type` (Validation, NotFound, Conflict, Failure, Unauthorized, Forbidden, Unexpected, custom), `Code`, `Description`, `Metadata` | `ResultStatus`; only `ValidationError` carries a code | reasons; a code only through metadata |
| HTTP | no package; a central mapper is about 10 lines | `Ardalis.Result.AspNetCore` writes validation errors as a plain list, not problem details, and no codes ([#193](https://github.com/ardalis/Result/issues/193)) | AspNetCore package in preview |

ErrorOr wins because each error already carries what an RFC 9457 response needs: a type that picks
the status, a stable code for the `code` extension, and a description for `detail`. Its success path
doesn't allocate. Two traps go into the rule: `default(ErrorOr<T>)` counts as success, and `.Value` on
an error returns `default` silently, so results are read with `Match`, `Switch` or `IsError`.

C# unions (C# 15, .NET 11, November 2026) may make a library unnecessary later; they don't exist on
net10.0.

## 3. Status mapping

| Error type | Status | Why |
| --- | --- | --- |
| Validation | 400, `TypedResults.ValidationProblem` with the field errors | The request is malformed or a field is invalid |
| NotFound | 404 | |
| Conflict | 409 | The record's current state forbids the action (already paid) |
| Failure | 422 | The request is well formed but breaks a business rule |

Unauthorized and Forbidden map to 401 and 403 when a project uses them; anything else is a 500.

## 4. Templates

Unchanged: the greeting example has no expected failure, so it follows CS-26 as it is, and adding
ErrorOr there would be an unused dependency. A project adds the package and its mapper with its first
expected failure.
