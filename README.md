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

## SQL Agent (Web Chat UI)

An AI agent can query the `VoterView` and `VoterEventView` materialized views via natural language.

```bash
# Set the LLM model (defaults to openai:gpt-4o)
export VOTER_REG_MODEL=openai:gpt-4o
export OPENAI_API_KEY=sk-...

# Start the web chat UI
uv run uvicorn apps.agent.web:app --host 127.0.0.1 --port 7932
```

Then open [http://127.0.0.1:7932](http://127.0.0.1:7932) in your browser.

Sample questions:
- How many people are registered to vote in Durham County?
- What is the breakdown of party affiliation among voters aged 18–25 vs 65+?
- What percentage of voters who voted in the 2020 General also voted in the 2022 Primary?

The agent has two tools:
- **run_sql_query** — generates and executes a SQL query, returns a markdown table
- **run_python_code** — executes LLM-written Python in a secure [Monty](https://github.com/pydantic/monty) sandbox, with `run_sql_query` available for chaining multiple queries

## Development

```bash
# Run development server
uv run manage.py runserver

# Run tests
uv run pytest

# Run linters
uv run pre-commit run --all-files
```
