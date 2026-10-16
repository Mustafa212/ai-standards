# Adopt: what each stack's standard configs assume

Read your stack's section in step 1, and report anything that doesn't fit at Gate 1.

## TypeScript

- Note the module system (`"type": "module"` or CommonJS) and the test runner.
- The standard check runs **Vitest**, and the standard `tsconfig.json` assumes ESM.
- A Jest suite is migrated first, as its own commit before adoption, or the user stops here. The
  migration is usually mechanical: `vi` for `jest`, and imports from `vitest`.
- A CommonJS project keeps its own `tsconfig.json`.

## Python

- Note the layout. The standard configs assume `src/<package>/` and `tests/`.
