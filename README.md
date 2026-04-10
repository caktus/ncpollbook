<!-- omit in toc -->
# NC Pollbook

[![tests](https://github.com/caktus/ncpollbook/actions/workflows/tests.yml/badge.svg)](https://github.com/caktus/ncpollbook/actions/workflows/tests.yml)

NC Pollbook is an exploratory Django web app for importing, loading, and analyzing North Carolina State Board of Elections (NCSBE) voter registration and history data with LLMs.

It combines a Django/PostgreSQL ETL pipeline and materialized views with a Pydantic AI SQL agent that answers analytical questions over the voter dataset in CLI and web chat interfaces.

Built with Django 6.x, PostgreSQL 18, and `django-pgviews-redux` for materialized views.

- [Setup](#setup)
- [Loading Data](#loading-data)
- [SQL Agent (Web Chat UI)](#sql-agent-web-chat-ui)
- [SQL Agent (CLI)](#sql-agent-cli)
- [Development](#development)

## Setup

**Prerequisites:** Python 3.14+, PostgreSQL 18, [`uv`](https://docs.astral.sh/uv/)

```bash
# Install dependencies
uv sync

# Configure database (defaults to postgresql://postgres@localhost:5432/ncpollbook)
export DATABASE_URL=postgresql://user:password@localhost:5432/yourdb

# Apply migrations
uv run manage.py migrate
uv run manage.py sync_pgviews

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

The model is configured via the Django admin under **Agent > Tool Models**. Add a `ToolModel` record
for each tool (`sql_gen`, `voter_agent`), or add one with no tool name as a default for all tools.

```bash
# Start the web chat UI
uv run uvicorn apps.agent.web:app --host 127.0.0.1 --port 7932
```

Then open [http://127.0.0.1:7932](http://127.0.0.1:7932) in your browser.

## SQL Agent (CLI)

A terminal alternative to the web UI with step-by-step output and a per-run summary of model
response time, tool execution time, and tokens/second.

```bash
# Interactive mode — type questions at the prompt, quit to exit
uv run manage.py agent cli

# Single question mode
uv run manage.py agent cli -q "how many active voters are in Durham County?"

# Inspect agent system prompts
uv run manage.py agent prompts
uv run manage.py agent prompts --name sql_gen
uv run manage.py agent prompts --name voter
```

Each run prints:
- **Thinking** panels — the model's internal reasoning (when supported by the model)
- **→ tool_name(args)** — each tool call as it is issued
- **↩ tool result** — a truncated preview of each tool response
- **Answer** — the final markdown answer
- **Run summary** table — step name, elapsed time, input/output tokens, and tokens/second

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

# Run tests (LLM evals skipped by default)
uv run pytest

# Run only LLM-judge evals (requires ollama or another local model running)
uv run pytest -m llm

# Run all tests including LLM evals
uv run pytest -m ''

# Run linters
uv run pre-commit run --all-files
```
