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
- **CS-12 [review]** Tests that touch data run against a real database (Testcontainers, reset between tests with Respawn or a rolled-back transaction), not an in-memory provider or a SQLite fake.
- **CS-13 [review]** One public type per file, and the file is named after it.
- **CS-14 [review]** Language keywords over runtime type names (`int`, not `Int32`). The IDE suggests it; no build check can (IDE0049 runs only in the IDE).
- **CS-18 [review]** Set an authorization `FallbackPolicy` that requires an authenticated user, so an endpoint with no authorization metadata fails closed; public endpoints opt out with `[AllowAnonymous]`, and static files that need protection are served after `UseAuthorization`. An endpoint that needs more than a signed-in user names a policy (`[Authorize(Policy = …)]`), and role names live only in policy definitions, so a permission change is one edit.
- **CS-19 [review]** Every `decimal` property has an explicit precision and scale (`HasPrecision`, or once in `ConfigureConventions`). Without it, SQL Server silently truncates values.
- **CS-20 [review]** An entity two users can edit at once carries a concurrency token (`IsRowVersion()`; on PostgreSQL a `uint` mapped to `xmin`). The token the client read comes back with the update (a `version` field or an `If-Match` ETag) and is set as the token's `OriginalValue` before saving. `DbUpdateConcurrencyException` becomes 409 Conflict (412 when an `If-Match` precondition failed), never a silent last write wins.
- **CS-21 [review]** Changes in one use case that must succeed together are saved with one `SaveChangesAsync`, which EF runs as one transaction; don't save per item in a loop. Several saves that must still be atomic share one explicit transaction, run through `Database.CreateExecutionStrategy()` when retry-on-failure is on. A batch job over independent records saves per record or per chunk, so one failure doesn't undo or block the rest.
- **CS-22 [review]** Every model change ships with its migration, and a test asserts that `db.Database.HasPendingModelChanges()` is false.
- **CS-23 [review]** Read every generated migration before merging: a rename must not come out as drop-and-add (use `RenameColumn`), and a column that becomes required gets a deliberate default or a data step. Never accept a scaffolded `0` or empty-string backfill on a money or reference column.
- **CS-24 [tool]** Read the current time only from an injected `TimeProvider`. `DateTime.Now`, `UtcNow` and `Today`, and `DateTimeOffset.Now` and `UtcNow`, are banned outside tests (RS0030), so tests control the clock.
- **CS-25 [review]** Check for null with `is null`, `is not null` or `is { } x`, which never call a user-overloaded `==`. Inside expression trees (EF Core and other `IQueryable` queries), where patterns are compile error CS8122, `== null` is correct.

| Task | Command |
| --- | --- |
| Everything CI runs | `bash .ai-standards/check.sh` |
| Fix formatting and style | `dotnet format` |
| Tests | `dotnet test` |
