<!-- omit in toc -->
# NC Pollbook

[![tests](https://github.com/caktus/ncpollbook/actions/workflows/tests.yml/badge.svg)](https://github.com/caktus/ncpollbook/actions/workflows/tests.yml)
[![docker-publish](https://github.com/caktus/ncpollbook/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/caktus/ncpollbook/actions/workflows/docker-publish.yml)

NC Pollbook is an exploratory Django web app for importing, loading, and analyzing North Carolina State Board of Elections (NCSBE) voter registration and history data with LLMs.

It combines a Django/PostgreSQL ETL pipeline and materialized views with a Pydantic AI SQL agent that answers analytical questions over the voter dataset in CLI and web chat interfaces.

Built with Django 6.x, PostgreSQL 18, and `django-pgviews-redux` for materialized views.

- [Setup](#setup)
- [Loading Data](#loading-data)
- [Model Providers](#model-providers)
  - [LM Studio (local, default)](#lm-studio-local-default)
  - [AWS Bedrock](#aws-bedrock)
  - [Anthropic API](#anthropic-api)
- [SQL Agent (OpenAI-Compatible API)](#sql-agent-openai-compatible-api)
- [SQL Agent (Web Chat UI)](#sql-agent-web-chat-ui)
- [SQL Agent (CLI)](#sql-agent-cli)
- [Docker Deployment](#docker-deployment)
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

## Model Providers

Models are configured via the Django admin under **Agent > Tool Models**. Load the default fixture to get started:

```bash
uv run manage.py loaddata agent_models
```

This configures `lmstudio:mistralai/ministral-3-3b` for the `voter_agent` tool and
`bedrock:us.anthropic.claude-haiku-4-5-20251001-v1:0` for `sql_gen`.

### LM Studio (local, default)

1. Download and install [LM Studio](https://lmstudio.ai/).
2. Search for and download **mistralai/ministral-3-3b** (the default model).
3. Start the local inference server (listens on `http://localhost:1234/v1`):

```bash
lms server start
```

No API key is required — LM Studio is accessed with the placeholder key `lm-studio`.

### AWS Bedrock

Set the bearer token before starting the server:

```bash
export AWS_BEARER_TOKEN_BEDROCK=<your-token>
```

Model names use the `bedrock:` prefix (e.g. `bedrock:us.anthropic.claude-sonnet-4-6`).

### Anthropic API

Set the API key before starting the server:

```bash
export ANTHROPIC_API_KEY=<your-key>
```

Model names use the `anthropic:` prefix (e.g. `anthropic:claude-sonnet-4-6`).

## SQL Agent (OpenAI-Compatible API)

An OpenAI-compatible API (`/v1/chat/completions`, `/v1/models`) served by [django-bolt](https://bolt.farhana.li/).
Point LibreChat or any OpenAI-compatible client at `http://<host>:8000/v1` with model `voter-agent`.

Optionally protect the API with an API key by setting `AGENT_API_KEY` in the environment. Clients
send it as `Authorization: Bearer <key>`.

```bash
# Start the async API server (serves API, Django admin, and docs on port 8000)
uv run manage.py runbolt --dev

# Health endpoints (no auth required)
# GET /health  — liveness probe
# GET /ready   — readiness probe with service checks
# Django admin available at http://127.0.0.1:8000/admin/
```

## SQL Agent (Web Chat UI)

An AI agent can query the `VoterView` and `VoterEventView` materialized views via natural language.

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

## Docker Deployment

Build and test the production image locally using the deploy compose file:

```bash
# Build the production image
COMPOSE_FILE=docker-compose.deploy.yaml docker compose build

# Start the stack (web + PostgreSQL) using the deploy env file
COMPOSE_FILE=docker-compose.deploy.yaml docker compose up -d
```

Edit `docker-compose.deploy.env` to set `DJANGO_SECRET_KEY`, database credentials,
and any model provider API keys before deploying.

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
