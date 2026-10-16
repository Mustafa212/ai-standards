# Break shapes: dotnet stack rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md.

## CS-8

- Search: `\.Result\b|\.Wait\(\)|async void`
- Break: `var order = repository.GetAsync(id).Result;` (an `async void` event handler is allowed)

## CS-14

- Search: `\b(Int16|Int32|Int64|UInt16|UInt32|UInt64|String|Boolean|Double|Decimal|Object|Char|Byte)\b`
- Break: `Int32 count = 0;`, `String.IsNullOrEmpty(name)`
