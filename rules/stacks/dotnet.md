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
- **CS-10 [review]** Never return EF Core entities from an API; map them to DTOs.
- **CS-15 [review]** Filter, page and project in the database, never after loading rows into memory.
- **CS-16 [review]** No N+1 queries: load related data with `Include` or a projection.
- **CS-17 [review]** Reads that don't update use `AsNoTracking()`.
- **CS-11 [review]** Respect DI lifetimes (no scoped service inside a singleton), and read settings through `IOptions<T>`.
- **CS-12 [review]** Tests are named `Method_Scenario_Expected`, and test behavior against a real database where data matters (Testcontainers or Respawn).
- **CS-13 [review]** One public type per file, and the file is named after it.
- **CS-14 [review]** Language keywords over runtime type names (`int`, not `Int32`). The IDE suggests it; no build check can (IDE0049 runs only in the IDE).

| Task | Command |
| --- | --- |
| Everything CI runs | `bash .ai-standards/check.sh` |
| Fix formatting and style | `dotnet format` |
| Tests | `dotnet test` |
