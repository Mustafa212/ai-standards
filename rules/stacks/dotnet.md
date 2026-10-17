## Stack: .NET (C#)

- **CS-1 [tool]** Nullable reference types are on, and every warning is an error.
- **CS-2 [tool]** File-scoped namespaces, `using` directives outside the namespace with `System.*` first, explicit access modifiers, and `_camelCase` private fields.
- **CS-3 [tool]** `var` only when the type is obvious from the right side (`new`, a cast, a literal).
- **CS-4 [tool]** Catch only what you can handle: no `catch (Exception)` without a filter, and rethrow with `throw;`.
- **CS-5 [tool]** Pass the `CancellationToken` through every async I/O call.
- **CS-6 [tool]** Seal internal and private types, and make members `static` when they use no instance state.
- **CS-7 [tool]** `nameof(x)` instead of string literals for member names.
- **CS-8 [review]** Async all the way: no `.Result`, `.Wait()` or `async void` (except event handlers).
- **CS-9 [review]** Data types are records, or classes with `required` and `init` properties.
- **CS-10 [review]** Never bind requests to EF Core entities or return entities from an API: map both ways through request and response DTOs, so a client can't set fields it shouldn't (over-posting).
- **CS-15 [review]** Filter, page and project in the database, never after loading rows into memory.
- **CS-16 [review]** No N+1 queries: load related data with `Include` or a projection.
- **CS-17 [review]** Reads that don't update use `AsNoTracking()`.
- **CS-11 [review]** Respect DI lifetimes (no scoped service inside a singleton), and read settings through `IOptions<T>`.
- **CS-12 [review]** Tests that touch data run against a real database (Testcontainers or Respawn), not an in-memory provider.
- **CS-13 [review]** One public type per file, and the file is named after it.
- **CS-14 [review]** Language keywords over runtime type names (`int`, not `Int32`). The IDE suggests it; no build check can (IDE0049 runs only in the IDE).
- **CS-18 [review]** Set an authorization `FallbackPolicy` that requires an authenticated user, so a forgotten `[Authorize]` fails closed; public endpoints opt out with `[AllowAnonymous]`. Endpoints name a policy (`[Authorize(Policy = …)]`), and roles appear only inside policy definitions.
- **CS-19 [review]** Every `decimal` property has an explicit precision and scale (`HasPrecision`, or once in `ConfigureConventions`). Without it, SQL Server silently truncates values.
- **CS-20 [review]** An entity two users can edit at once carries a concurrency token (`IsRowVersion()`, or `xmin` on PostgreSQL), and `DbUpdateConcurrencyException` becomes a 409 Conflict, never a silent last write wins.
- **CS-21 [review]** A use case saves once, with one `SaveChangesAsync` at the end, which EF runs as one transaction. Never save inside a loop; saves that must succeed together share one explicit transaction.
- **CS-22 [review]** Every model change ships with its migration, and a test asserts that `db.Database.HasPendingModelChanges()` is false.
- **CS-23 [review]** Read every generated migration before merging: a rename must not come out as drop-and-add, and a column that becomes required needs a default or a data step.
- **CS-24 [tool]** Read the current time only from an injected `TimeProvider`. `DateTime.Now`, `UtcNow` and `Today`, and `DateTimeOffset.Now` and `UtcNow`, are banned outside tests (RS0030), so tests control the clock.
- **CS-25 [review]** Check for null with `is null`, `is not null` or `is { } x`, which no overloaded `==` can change. `== null` stays only inside EF Core query expressions, where patterns aren't allowed.

| Task | Command |
| --- | --- |
| Everything CI runs | `bash .ai-standards/check.sh` |
| Fix formatting and style | `dotnet format` |
| Tests | `dotnet test` |
