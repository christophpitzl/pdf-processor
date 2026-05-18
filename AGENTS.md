# Project Guidelines

## Code Style

- Follow **PEP 8** conventions for all Python code.
- Use **type hints** for all function signatures and class attributes.
- Prefer **f-strings** over `%` formatting or `.format()`.
- Use **4 spaces** for indentation (no tabs).
- Maximum line length: **88 characters** (compatible with Black formatter).
- Use **snake_case** for variables, functions, and methods; **PascalCase** for classes; **UPPER_CASE** for constants.

## Architecture

- **`src/`** — Main application package with a modular structure:
  - `src/processor/` — PDF parsing, text extraction, and manipulation logic
  - `src/cli/` — Command-line interface (Click or argparse)
  - `src/utils/` — Shared utilities (file I/O, logging, validation)
- **`tests/`** — Test suite mirroring the `src/` structure, using `pytest`.
- **`data/`** — Sample PDFs and test fixtures (tracked with Git LFS).
- Keep processing functions **pure** (no side effects) where possible; isolate I/O in dedicated modules.
- Use **dependency injection** for testability (e.g., pass file handles, config objects).

## Build and Test

- **Install**: `pip install -e ".[dev]"`
- **Lint**: `ruff check src/ tests/`
- **Format**: `black src/ tests/`
- **Type check**: `mypy src/`
- **Test**: `pytest --cov=src/`
- **Run**: `python -m src.cli --help`

## Conventions

- All PDF processing should handle **encrypted/invalid files gracefully** with clear error messages.
- Log via the `logging` module (not `print`); use structured logging for batch operations.
- Write **docstrings** for all public modules, classes, and functions (Google-style).
- Keep **Git LFS** tracking for `*.pdf` files — run `git lfs track "*.pdf"` before adding PDFs.
- Use `pathlib.Path` for all filesystem operations (not `os.path`).
- Prefer `dataclasses` or `Pydantic` models for data structures over plain dicts.

## Project Memory

- Config centralized in `src/config.py` via `Settings` dataclass with `from_env()` factory
- Defaults defined once in `Settings`; all other files reference it
- `.env.example` documents all env vars with defaults
- `docker-compose.yml` passes env vars with shell defaults (`${VAR:-default}`)