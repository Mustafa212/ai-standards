# Runners for the scripts and copier

The skills write `python3` and `uvx copier`. When one of them doesn't work on this machine, use the
first that does:

- **Python:** `python3`; else `python` (on Windows `python3` is often the Microsoft Store alias,
  which prints "Python was not found"); else `uv run --no-project python`.
- **copier:** `uvx copier` when `uv` exists; else `pipx run copier`; else
  `pip install --user copier`, then `copier`. With none of them, say so and stop (Windows:
  `winget install astral-sh.uv`).
- **Python projects** also need `uv` and `make` (Windows: `winget install astral-sh.uv`,
  `winget install ezwinports.make`).
