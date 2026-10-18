# Break shapes: dotnet clean-architecture rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md. The `[tool]` rules have one too, for projects whose architecture tests don't run yet.

## CLEAN-2

- Search, in the Domain project: `using Microsoft\.(EntityFrameworkCore|AspNetCore)|\[(Key|Table|Column|ForeignKey|JsonPropertyName)\b`
- Break: `using Microsoft.EntityFrameworkCore;` in `Domain/Orders/Order.cs`

## CLEAN-6

- Search, in the Application project: `using Microsoft\.AspNetCore|\b(HttpContext|IFormFile|IActionResult|IResult)\b`
- Break: `public sealed record UploadStatementCommand(IFormFile File);` in `Application/Features/Statements/UploadStatement/UploadStatementCommand.cs`

## CLEAN-7

- Search, in the Domain project: `public [^(]+\{ get; set; \}`
- Break: `public InvoiceStatus Status { get; set; }` on `Invoice`, set by a handler (`invoice.Status = InvoiceStatus.Paid;`) instead of `invoice.MarkPaid(payment)`

## CLEAN-8

- Search, in the Domain project: `public (virtual )?[A-Z]\w+\?? [A-Z]\w+ \{ get;` on an aggregate root whose type is another aggregate root
- Break: `public Customer Customer { get; private set; }` on `Invoice`, or a handler that changes `invoice.Lines[0].Quantity` directly

## CLEAN-9

- Search, in handlers: `ValidateAsync\(|BeginTransaction|_logger\.Log\w+\("Handling`
- Break: `var check = await validator.ValidateAsync(command, ct); if (!check.IsValid) …` repeated at the top of every handler

## CLEAN-10

- Search, in Application handlers: `\b(ISender|IMediator)\b|\w+Handler \w+[,)]` in a constructor
- Break: `public sealed class PayInvoiceHandler(IssueReceiptHandler receipts)`, or `await sender.Send(new IssueReceiptCommand(…), ct)` inside a handler

## CLEAN-11

- Search: `interface I\w*Repository|class \w*Repository<T>|IQueryable<T> (Query|GetAll|AsQueryable)`
- Break: `public interface IRepository<T> { IQueryable<T> Query(); }` next to handlers that also inject `IAppDbContext`

## CLEAN-12

- Search: `interface I(\w+)(Service|Manager|Helper)\b`, then a single `class \1\2 : I\1\2` and no other implementation
- Break: `public interface IInvoiceService` with one `InvoiceService : IInvoiceService`, registered only to be injected

## CLEAN-13

- Search, Glob in Application: `**/{Handlers,Validators,Dtos,Commands,Queries}/*.cs` at the top level, outside `Features/`
- Break: `Application/Handlers/CreateInvoiceHandler.cs` and `Application/Validators/CreateInvoiceValidator.cs`

## CLEAN-14

- Search, in query handlers: `SaveChangesAsync|\.Add\(|\.Remove\(|ExecuteUpdate|ExecuteDelete`
- Break: `GetInvoiceQueryHandler` that sets `invoice.LastViewedAt` and calls `SaveChangesAsync`
