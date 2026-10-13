## Stack: TypeScript

- **TS-1 [tool]** `strict`, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` stay on. No `any` (use `unknown` and narrow) and no non-null assertions (`!`).
- **TS-2 [tool]** Type-aware lint is on: no floating promises, exhaustive `switch` over unions, `import type` for type-only imports.
- **TS-3 [review]** Model the domain with discriminated unions and `readonly` types. Use classes only when you need behaviour plus state.
- **TS-4 [review]** Validate untrusted input at the edge with a schema (e.g. zod) and derive the TypeScript type from it.
- **TS-5 [review]** Named exports only. Test files sit next to the code: `foo.ts` → `foo.test.ts`.

| Task | Command |
| --- | --- |
| Everything CI runs | `npm run check` |
| Auto-fix format + lint | `npm run fix` |
| Tests (watch) | `npx vitest` |
