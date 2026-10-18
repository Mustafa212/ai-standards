# Break shapes: dotnet stack rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md.

## CS-8

- Search: `\.Result\b|\.Wait\(\)|async void`
- Break: `var order = repository.GetAsync(id).Result;` (an `async void` event handler is allowed)

## CS-14

- Search: `\b(Int16|Int32|Int64|UInt16|UInt32|UInt64|String|Boolean|Double|Decimal|Object|Char|Byte)\b`
- Break: `Int32 count = 0;`, `String.IsNullOrEmpty(name)`

## CS-10

- Search: `\[FromBody\]\s+\w+` or controller actions whose parameter type is an entity
- Break: `public async Task<IActionResult> Update(Customer customer) { db.Update(customer); … }`

## CS-12

- Search: `UseInMemoryDatabase|DataSource=:memory:`
- Break: `options.UseInMemoryDatabase("tests")`

## CS-18

- Search: `AddAuthorization\(` with no `FallbackPolicy`, or `\[Authorize\(Roles\s*=`
- Break: `[Authorize(Roles = "Admin")]`

## CS-19

- Search: `\bdecimal\??\s+\w+\s*\{\s*get;` with no `HasPrecision` or `Properties<decimal>` for it
- Break: `public decimal Amount { get; private set; }` and no precision in the model

## CS-20

- Search: editable aggregates with no `IsRowVersion|\[Timestamp\]`, or no `DbUpdateConcurrencyException` handling
- Break: `invoice.Status = InvoiceStatus.Paid; await db.SaveChangesAsync(ct);` on an entity with no concurrency token

## CS-21

- Search: `SaveChanges(Async)?\(` inside a `foreach` or `for` body
- Break: `foreach (var line in lines) { db.Add(line); await db.SaveChangesAsync(ct); }`

## CS-22

- Search: Glob `**/*Tests*/**/*.cs` with no `HasPendingModelChanges`
- Break: a model change with no migration, and no test that would catch it

## CS-23

- Search: `migrationBuilder\.(DropColumn|DropTable)` in `Migrations/`
- Break: `migrationBuilder.DropColumn(name: "Name", table: "Customers");` next to `AddColumn<string>(name: "FullName", …)`

## CS-25

- Search: `[!=]=\s*null\b` outside lambdas passed to `Where`, `Any`, `Select` or `OrderBy`
- Break: `if (customer == null) throw new NotFoundException(…);`

## CS-26

- Search: `throw new \w*(NotFound|Validation|BusinessRule|Domain|Conflict)\w*Exception\(`, and `\.Value\b` on an `ErrorOr` result with no `IsError` check before it
- Break: `if (invoice.IsPaid) throw new BusinessRuleException("Invoice is already paid.");` in a handler, caught and mapped to 409 by an exception handler
