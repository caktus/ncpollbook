# voter-reg

Web application for importing and searching North Carolina voter registration and history data.

Built with Django 6, PostgreSQL 18, and `django-pgviews-redux` for materialized views.

## Setup

**Prerequisites:** Python 3.14+, PostgreSQL 18, [`uv`](https://docs.astral.sh/uv/)

```bash
# Install dependencies
uv sync

# Configure database (defaults to postgresql://postgres@localhost:5432/ncpollbook)
export DATABASE_URL=postgresql://user:password@localhost:5432/yourdb

# Apply migrations
uv run manage.py migrate

# Create superuser (optional)
uv run manage.py createsuperuser
```

## Loading Data

```bash
# Download NCSBE files and load into PostgreSQL, then refresh materialized views
uv run manage.py ncsbe etl

# Only refresh materialized views (skip download/load)
uv run manage.py ncsbe etl --refresh-only

# Inspect the first 100 rows of each source file
uv run manage.py ncsbe peek
```

Data is cached in `scratch/data/` after the first download.

## Development

```bash
# Run development server
uv run manage.py runserver

# Run tests
uv run pytest

# Run linters
uv run pre-commit run --all-files
```
