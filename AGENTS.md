# AGENTS.md

This file provides guidance when working with code in this repository.

## Project Overview

This is a web application for importing and searching voter registration and history data from North Carolina. 

- This is a Django 6.x project built on Python 3.14.
- The main database is PostgreSQL 18.

## Development Commands

### Environment Setup

- `uv` is used for Python dependency management.
- Install Python dependencies: `uv sync`
- Add Python dependencies: `uv add <library>` or `uv add --group dev <library>` for dev-only
- Run database migrations: `uv run manage.py migrate`
- Create superuser: `uv run manage.py createsuperuser`
- You can run generic Python commands using `uv run <command>`

### Running the Application

- Start the development server: `uv run manage.py runserver`

### Testing

- Run tests with pytest: `uv run pytest`
- Tests are located in the `tests/` directory and follow standard pytest-django and pytest-mock conventions.
- factoryboy is used for test data creation.
- **Efficient Testing:** Test filters, models, and business logic directly using filtersets or model methods rather than making HTTP requests to views. Use one focused smoke test for end-to-end integration verification. This dramatically improves test speed (view tests are 3-5x slower than unit tests).
- **Test Organization:** Group related tests in test classes by functionality with fast unit tests first and slower integration tests last.

### Code Quality

- Run pre-commit hooks: `uv run pre-commit run --all-files`
- Check for missing migrations: `uv run manage.py makemigrations --check`
- After generating migrations and adding them to git, always run `pre-commit` again to ensure they are formatted by the `ruff` check.
- Always add or update tests when changing code, even if not explicitly asked. New features and bug fixes should include focused tests, not exhaustive ones.
- Typing: Always use modern Python 3.12+ typing:
  - Use built-in generics (e.g., `list[str]`, `dict[int, str]`) instead of `typing` imports.
  - Use the `|` operator for unions (e.g., `str | None`) instead of `Optional` or `Union`.
  - Use `collections.abc` (e.g., `Sequence`, `Iterable`) for flexible input arguments.
- Path Handling: Always use `pathlib.Path` for file system operations. Avoid `os.path`.
  - Type hint paths as `pathlib.Path` for internal logic and `pathlib.Path | str` for public API entry points.
  - Prefer path operators (e.g., `path / "subdir"`) and methods like `.read_text()` or `.write_text()`.
- Imports: Always add imports to the top of the file, not inside functions or methods.

### Agent Workflow

- Always maintain a detailed todo/checklist list.
- Always run full test suite and ruff pre-commit hooks as the last tasks in your todo list.
