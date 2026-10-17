# Break shapes: base rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors: a search to
start from (Grep, or Glob for file names) and a short bad snippet. Never rendered into AGENTS.md.

## RDB-5

- Search: `^\s*(//|#)\s*(await\s+|return\s+)?[\w.]+\(.*\)\s*;?\s*$` (commented-out code)
- Break: `// await sendReminder(invoice);`

## RDB-9

- Search: `\w\(([^()]*,\s*)?(true|false|True|False)\s*\)` (a boolean flag argument)
- Break: `send(user, true)`

## RDB-10

- Search: Glob `**/*{util,Util,helper,Helper,common,Common}*`
- Break: `src/utils.ts`, `Helpers/StringHelper.cs`

## TST-4

- Search, in test files: `sleep\(|Thread\.Sleep|Task\.Delay|setTimeout|Future\.delayed|waitForTimeout`
- Break: `await Task.Delay(500); Assert.True(job.IsDone);`

## ERR-4

- Search: `(?i)(log|console|print)\w*[.(].*(password|token|secret|api_?key)`
- Break: `logger.info(f"signed in, token={token}")`

## DES-8

- Search: `(AnyAsync|ExistsAsync|exists|any)\(` right before an insert of the same key
- Break: `if (!await db.Invoices.AnyAsync(i => i.Number == number)) db.Invoices.Add(invoice);`

## DES-9

- Search: `(DueDate|IssueDate|BirthDate)\b.*\bDateTime\b`
- Break: `public DateTime DueDate { get; set; }` for a calendar date

## ERR-6

- Search: `\b(double|float)\s+\w*(Amount|Price|Total|Balance|Tax|Fee|amount|price|total|balance)`
- Break: `double total = lines.Sum(l => l.Price * l.Quantity);`

## ERR-7

- Search: `(FindAsync|SingleOrDefaultAsync|findById|get_object_or_404)\(\s*\w*[Ii]d\s*\)` with no owner or tenant filter
- Break: `var invoice = await db.Invoices.FindAsync(id); return invoice;`

## ERR-8

- Search: `(request|dto|body|command)\.(Price|Total|Amount|Discount|Role)\b` stored without a lookup
- Break: `invoice.Total = request.Total;`

## ERR-9

- Search: `(ex|exception|err)\.(Message|StackTrace|stack)\b` inside a response
- Break: `return StatusCode(500, ex.Message);`

## DES-10

- Search: endpoints that return `List<`, `IEnumerable<`, `list[`, an array or `ToListAsync()` with no page parameters
- Break: `[HttpGet] public Task<List<ProjectDto>> GetAll(CancellationToken ct) => db.Projects.Select(p => new ProjectDto(p.Id, p.Name)).ToListAsync(ct);`

## ERR-10

- Search: `IFormFile|UploadFile|multer|\.FileName\b|\.originalname\b`
- Break: `var path = Path.Combine("wwwroot/uploads", file.FileName);`
