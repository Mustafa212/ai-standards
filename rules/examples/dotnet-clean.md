# Break shapes: dotnet clean-architecture rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md.

## CLEAN-2

- Search, in the Domain project: `using Microsoft\.(EntityFrameworkCore|AspNetCore)|\[(Key|Table|Column|ForeignKey|JsonPropertyName)\b`
- Break: `using Microsoft.EntityFrameworkCore;` in `Domain/Orders/Order.cs`
