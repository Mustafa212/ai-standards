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
