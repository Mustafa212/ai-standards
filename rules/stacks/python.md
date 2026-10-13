## Stack: Python

- **PY-1 [tool]** `mypy --strict` passes. Every function is fully annotated; no `Any` in public signatures.
- **PY-2 [tool]** Ruff is the formatter and linter: `pathlib` over `os.path`, no `print` (use `logging`), no blind `except Exception`.
- **PY-3 [review]** Data is `@dataclass(frozen=True)` (or pydantic at I/O edges); fixed sets of values are `Enum`s.
- **PY-4 [review]** `src/` layout. Tests in `tests/` mirror module paths: `src/pkg/billing.py` → `tests/test_billing.py`.

| Task | Command |
| --- | --- |
| Everything CI runs | `make check` |
| Auto-fix format + lint | `make fix` |
| Tests | `make test` |
