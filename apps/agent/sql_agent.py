"""SQL analysis agent for querying VoterView and VoterEventView materialized views.

Two tools are registered on voter_agent:
- run_sql_query(question): generate + validate + execute SQL, return markdown table
- run_python_code(code): execute LLM-written Python via Monty; exposes run_sql_query
  as a safe external function so the LLM can chain multiple queries programmatically
"""

import logging
from dataclasses import dataclass
from datetime import date

import logfire
import psycopg
import pydantic_monty
from django.conf import settings
from django.db import connection as django_connection
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets.function import FunctionToolset

from apps.agent.models import AgentTool, ToolModel
from apps.agent.sql_examples import SQL_EXAMPLES
from apps.ncsbe.models import VoterEventView, VoterView

# 'if-token-present' means nothing will be sent (and the example will work) if you don't have logfire configured
logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_psycopg()
logfire.instrument_pydantic_ai()

logger = logging.getLogger(__name__)

_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"


def resolve_model(model_str: str) -> str | OpenAIChatModel:
    """Resolve a model string to a pydantic-ai model.

    Supports the ``lmstudio:<model-name>`` prefix, which connects to LM Studio's
    local OpenAI-compatible server at ``http://localhost:1234/v1``.
    All other strings are returned as-is for pydantic-ai's built-in resolution.
    """
    if model_str.startswith("lmstudio:"):
        model_name = model_str[len("lmstudio:") :]
        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(base_url=_LM_STUDIO_BASE_URL, api_key="lm-studio"),
        )
    return model_str


_DJANGO_TO_SQL: dict[str, str] = {
    "BigAutoField": "bigint",
    "BigIntegerField": "bigint",
    "SmallIntegerField": "smallint",
    "IntegerField": "integer",
    "FloatField": "double precision",
    "CharField": "varchar",
    "TextField": "text",
    "DateField": "date",
    "DateTimeField": "timestamp with time zone",
    "BooleanField": "boolean",
}


def get_view_schema(model_class: type) -> str:
    """Return a DDL-style schema string describing a materialized view model."""
    table_name = model_class._meta.db_table
    fields = model_class._meta.fields
    lines = [f"CREATE TABLE {table_name} ("]
    for i, field in enumerate(fields):
        sql_type = _DJANGO_TO_SQL.get(field.get_internal_type(), "text")
        nullable = "NULL" if field.null else "NOT NULL"
        comma = "," if i < len(fields) - 1 else ""
        comment = f"  -- {field.db_comment}" if field.db_comment else ""
        lines.append(f"    {field.column} {sql_type} {nullable}{comma}{comment}")
    lines.append(");")
    return "\n".join(lines)


def _get_async_conninfo() -> dict[str, str | int]:
    """Return psycopg connection kwargs from Django's database settings."""
    db = django_connection.settings_dict
    return {
        "host": db.get("HOST", "localhost"),
        "port": int(db.get("PORT") or 5432),
        "dbname": db["NAME"],
        "user": db.get("USER", ""),
        "password": db.get("PASSWORD", "") or "",
    }


def _rows_to_markdown(description: list, rows: list) -> str:
    if not rows:
        return "_No results_"
    cols = [d.name for d in description]
    header = "| " + " | ".join(cols) + " |"
    separator = "| " + " | ".join(["---"] * len(cols)) + " |"
    data_rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows[:100]]
    result = "\n".join([header, separator, *data_rows])
    if len(rows) > 100:
        result += f"\n\n_(showing 100 of {len(rows)} rows)_"
    return result


# ---------------------------------------------------------------------------
# SQL generation agent (internal — not exposed via web UI directly)
# ---------------------------------------------------------------------------


@dataclass
class SqlDeps:
    conn: psycopg.AsyncConnection


class Success(BaseModel):
    """Response when SQL could be successfully generated."""

    sql_query: str = Field(description="Generated SQL query")
    explanation: str = Field("", description="Explanation of the SQL query, as markdown")


class InvalidRequest(BaseModel):
    """Response when the user input didn't include enough information to generate SQL."""

    error_message: str


type Response = Success | InvalidRequest

sql_gen_agent: Agent[SqlDeps, Response] = Agent(
    resolve_model(settings.VOTER_REG_MODEL),
    output_type=Response,  # type: ignore[arg-type]
    deps_type=SqlDeps,
    retries=2,
    defer_model_check=True,
)


@sql_gen_agent.system_prompt
async def _sql_system_prompt() -> str:
    voter_schema = get_view_schema(VoterView)
    voter_event_schema = get_view_schema(VoterEventView)
    return f"""\
You are a PostgreSQL expert. Write a SQL SELECT query that answers the user's question
about North Carolina voter registration and history data.

Only query the views defined below. Do NOT reference any other tables.
Do NOT include any PII (names, addresses, phone numbers, SSNs).

Today's date: {date.today()}

{voter_schema}

{voter_event_schema}

Join the two views using the `ncid` column.
Always UPPERCASE place names, like county names, in your SQL queries to ensure correct matching.
By default, filter by registration_status_code = 'A' (active voters) unless the question indicates otherwise.

Example queries:

{chr(10).join(SQL_EXAMPLES)}
"""


def get_tool_model(tool_name: str | None) -> str | OpenAIChatModel:
    """Return the model configured for a tool, falling back to settings.

    Lookup order:
    1. ToolModel with matching tool_name
    2. ToolModel with tool_name=NULL (default)
    3. settings.VOTER_REG_MODEL
    """
    record = (
        ToolModel.objects.filter(tool_name=tool_name).select_related("model").first()
        or ToolModel.objects.filter(tool_name=None).select_related("model").first()
    )
    if record:
        return resolve_model(record.model.name)
    return resolve_model(settings.VOTER_REG_MODEL)


_DISALLOWED_STATEMENTS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"}


def _is_safe_select_query(sql: str) -> bool:
    """Return True if sql contains SELECT and no disallowed write/DDL statements."""
    upper = sql.upper()
    if "SELECT" not in upper:
        return False
    words = set(upper.split())
    return words.isdisjoint(_DISALLOWED_STATEMENTS)


@sql_gen_agent.output_validator
async def _validate_sql(ctx: RunContext[SqlDeps], result: Response) -> Response:
    if isinstance(result, InvalidRequest):
        return result
    result.sql_query = result.sql_query.replace("\\", "")
    if not _is_safe_select_query(result.sql_query):
        raise ModelRetry("Please create a SELECT-only query with no data-modifying statements")
    try:
        await ctx.deps.conn.execute(f"EXPLAIN {result.sql_query}")
    except psycopg.Error as e:
        raise ModelRetry(f"Invalid query: {e}") from e
    return result


# ---------------------------------------------------------------------------
# Voter agent toolset
# ---------------------------------------------------------------------------


async def _run_sql_query(question: str) -> str:
    """Generate and execute a SQL query. Returns results as a markdown table."""
    async with await psycopg.AsyncConnection.connect(**_get_async_conninfo()) as conn:
        deps = SqlDeps(conn=conn)
        result = await sql_gen_agent.run(
            question, deps=deps, model=get_tool_model(AgentTool.SQL_GEN)
        )
        if isinstance(result.output, InvalidRequest):
            return f"Could not generate query: {result.output.error_message}"
        sql = result.output.sql_query
        explanation = result.output.explanation
        logger.info("Running SQL: %s", sql)
        async with conn.cursor() as cur:
            await cur.execute(sql)
            rows = await cur.fetchall()
            table = _rows_to_markdown(cur.description, rows)
        parts = [f"```sql\n{sql}\n```"]
        if explanation:
            parts.append(explanation)
        parts.append(table)
        return "\n\n".join(parts)


voter_toolset: FunctionToolset = FunctionToolset()


@voter_toolset.tool_plain
async def run_sql_query(question: str) -> str:
    """Answer a natural-language question about North Carolina voter data.

    Pass a plain-English question such as "how many active voters are in Durham County?"
    Do NOT pass SQL — SQL is generated internally from the question.
    Returns results as a markdown table.
    """
    return await _run_sql_query(question)


_MONTY_TYPE_STUBS = """\
async def run_sql_query(question: str) -> str:
    raise NotImplementedError()
"""


# @voter_toolset.tool_plain
async def run_python_code(code: str) -> str:
    """Execute Python code written to analyse voter data.

    The code may call `run_sql_query(question: str) -> str` to query the database.
    Use this tool when you need to chain multiple queries or perform calculations
    across query results. Code runs in a secure sandbox (Monty) with no filesystem
    or network access beyond the provided functions.

    Example:
        result1 = await run_sql_query("total active voters by county")
        result2 = await run_sql_query("total voters by county")
        print(result1)
        print(result2)
    """
    m = pydantic_monty.Monty(
        code,
        type_check=True,
        type_check_stubs=_MONTY_TYPE_STUBS,
    )
    result = await pydantic_monty.run_monty_async(
        m,
        external_functions={"run_sql_query": _run_sql_query},
    )
    output = str(result.output) if result.output is not None else ""
    if result.stdout:
        output = result.stdout + ("\n" + output if output else "")
    return output or "_No output_"


# ---------------------------------------------------------------------------
# Main voter agent (exposed via web UI)
# ---------------------------------------------------------------------------

voter_agent: Agent[None, str] = Agent(
    resolve_model(settings.VOTER_REG_MODEL),
    defer_model_check=True,
    instructions="""\
You are a voter data analyst. You help users explore North Carolina voter
registration and election history data.

Always pass plain-English questions to run_sql_query — never compose or pass SQL yourself.
Use run_python_code when you need to chain multiple queries or compute cross-query statistics.

Present results clearly in markdown. Never expose PII (names, addresses, phone
numbers). Reference voters by ncid only if needed.""",
    toolsets=[voter_toolset],
)
