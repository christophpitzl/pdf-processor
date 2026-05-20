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
- Entities only added to filename if `{entities}` is specified in `FILENAME_PATTERN`

## Ollama Integration

- **Recommended model**: `gemma4:e2b` — returns clean JSON without markdown code blocks
- **JSON parsing**: Code in `src/main.py` handles models that wrap JSON in markdown (```json ... ```)
- **Connection check**: `check_ollama_connection()` method validates Ollama availability at startup
- **Error handling**: Enhanced logging shows full response content when JSON parsing fails
- **Default config**: `OLLAMA_BASE_URL=http://ollama.pitzl.net:11434`, `OLLAMA_MODEL=gemma4:e2b`
- **Entities**: Only requested from AI model when `{entities}` is in the filename pattern

## Docker Version Tag Strategy

- **Builds triggered only by Git tags** (not branch pushes)
- **`latest` tag**: Updated on Git version tags (e.g., `v1.0.0`, `v0.3.0`)
- **Version tags**: `v0.3.0`, `v0.3`, `v0` (semantic versioning, major/minor/major.minor patterns)
- **No automatic `main` branch builds** - use version tags for all releases
- **User guidance**: 
  - Production users should use specific version tags or `latest` (stable releases only)
  - No `main` tag - all builds are version-tagged releases
- **Multi-arch**: Images built for both `linux/amd64` and `linux/arm64`
- **Base image**: `python:3.11-alpine` (smaller, more secure than Debian-based)
- **Workflow file**: `.github/workflows/docker-publish.yml` handles tagging logic