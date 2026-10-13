# Rule regression tests

Each file here deliberately breaks one or more `[tool]` rules. The first line declares which lint
rule IDs **must** fire:

```
// expect: max-params, @typescript-eslint/no-magic-numbers
# expect: PLR0913, T201
```

`scripts/test-templates.sh` copies these files into freshly generated projects and fails if any
expected rule stays silent. That catches rules that silently stop working after a tool upgrade or
a config edit.

Files under `<stack>/` run against every org. Files under `<stack>/<org>/` run only for that org
(for org-specific rules such as banned imports).

When you add a `[tool]` rule, add a violation here.
