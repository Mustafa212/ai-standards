# Break shapes: dotnet modular-monolith rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md. The `[tool]` rules have one too, for projects whose architecture tests don't run yet.

## MOD-1

- Search, in `*.csproj` of a module: `<ProjectReference Include="[^"]*\.Modules\.\w+/` to a project that doesn't end in `.Contracts`
- Break: `Modules.Billing.csproj` referencing `Modules.Invoicing.csproj` to call its `IssueInvoiceHandler`

## MOD-2

- Search, in a module project: `^public (sealed |static |abstract )?(class|record|interface|enum) ` outside the `<Module>Module` file
- Break: `public sealed class InvoiceRepository` in `Modules.Invoicing/`

## MOD-3

- Search: `modelBuilder\.Entity<\w+>` in one module's `DbContext` for an entity that lives in another module, and `HasDefaultSchema` missing from a module's `DbContext`
- Break: `BillingDbContext` mapping `Invoice` from `Modules.Invoicing`

## MOD-4

- Search: `BeginTransaction|TransactionScope` in code that calls two modules' facades or saves two modules' contexts
- Break: `using var tx = await billingDb.Database.BeginTransactionAsync(ct); … await invoicingDb.SaveChangesAsync(ct);`

## MOD-5

- Search: SQL or LINQ joining tables of two schemas (`FROM invoicing\.\w+ JOIN billing\.`), or one module's `DbContext` opened from another module
- Break: `var unpaid = from i in invoicingDb.Invoices join p in billingDb.Payments on …`

## MOD-6

- Search, Glob in a module: `**/{Handlers,Services,Validators,Dtos}/*.cs`
- Break: `Modules.Invoicing/Handlers/IssueInvoiceHandler.cs` next to `Modules.Invoicing/Dtos/InvoiceDto.cs`

## MOD-7

- Search: a module moved into its own deployable (`Program.cs` under `src/*.Modules.*`, or its own Dockerfile) with no recorded reason
- Break: `src/App.Modules.Invoicing/Program.cs` added "so it can scale later", with no load figures
