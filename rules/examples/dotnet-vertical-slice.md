# Break shapes: dotnet vertical-slice rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md. The `[tool]` rules have one too, for projects whose architecture tests don't run yet.

## VSA-3

- Search, Glob: `Features/*/*{Request,Response,Dto}.cs` (one directly under a feature, used by several slices), or a `using` of another slice's namespace for its request or response
- Break: `Features/Invoices/InvoiceDto.cs` returned by both `GetInvoice` and `ListInvoices`, or `Features/Common/BaseRepository.cs`

## VSA-4

- Search, in handlers: `\w+\.(Status|State|Total|Balance) = ` (a handler setting an entity's state field by hand), and `class \w+Service\b` under `Features/`
- Break: `invoice.Status = InvoiceStatus.Paid; invoice.PaidAt = now;` in two handlers instead of `invoice.MarkPaid(now)`

## VSA-5

- Search: `app\.Map(Get|Post|Put|Patch|Delete)\(` in `Program.cs`, or the same `MapGroup("/<prefix>")` in more than one file
- Break: `Program.cs` mapping every route itself: `app.MapPost("/invoices/{id}/pay", …)`

## VSA-6

- Search, in a slice: `using \w+(\.\w+)*\.Features\.(\w+)\.` whose feature isn't the slice's own
- Break: `PayInvoiceHandler` injecting `IssueReceiptHandler` from `Features/Receipts/`

## VSA-7

- Search, in `Domain/`: `using \w+(\.\w+)*\.Features\.`
- Break: `Domain/Invoices/Invoice.cs` returning a `Features.Invoices.GetInvoice.InvoiceResponse`

## VSA-8

- Search, in tests: `UseInMemoryDatabase|Mock<(I\w*DbContext|DbSet)` or a handler test with no endpoint test for the same slice
- Break: `PayInvoiceHandlerTests` built on `UseInMemoryDatabase("test")`, and no `PayInvoiceEndpointTests`
