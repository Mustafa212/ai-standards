## Stack: Python

- **PY-1 [tool]** `mypy --strict` passes. Every function is fully annotated; no `Any` in public signatures.
- **PY-2 [tool]** Ruff is the formatter and linter: `pathlib` over `os.path`, no `print` (use `logging`), no blind `except Exception`.
- **PY-3 [review]** Data is `@dataclass(frozen=True)` (or pydantic at I/O edges); fixed sets of values are `Enum`s.
- **PY-5 [tool]** Text files are opened with an explicit `encoding="utf-8"`; the platform default (cp1252 on Windows) corrupts non-ASCII text such as Arabic. No mutable default arguments (`def f(x=[])`).
- **PY-4 [review]** `src/` layout. Tests in `tests/` mirror module paths: `src/pkg/billing.py` → `tests/test_billing.py`.
- **PY-6 [tool]** No boolean positional arguments (Ruff `FBT`): make them keyword-only, `def send(user, *, urgent: bool)`.

| Task | Command |
| --- | --- |
| Everything CI runs | `make check` |
| Auto-fix format + lint | `make fix` |
| Tests | `make test` |
