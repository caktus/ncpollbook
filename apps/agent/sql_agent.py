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
from pydantic_ai.toolsets.function import FunctionToolset

from apps.ncsbe.models import VoterEventView, VoterView

# 'if-token-present' means nothing will be sent (and the example will work) if you don't have logfire configured
logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_psycopg()
logfire.instrument_pydantic_ai()

logger = logging.getLogger(__name__)

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
    settings.VOTER_REG_MODEL,
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

VoterView status codes: A=ACTIVE, D=DENIED, I=INACTIVE, R=REMOVED, S=TEMPORARY
VoterEventView election_type values: PRIMARY, SECOND_PRIMARY, GENERAL, RUNOFF, MUNICIPAL, SPECIAL, OTHER
VoterEventView voting_method: exclude 'ELIGIBLE DID NOT VOTE' and 'TRANSFER' when computing turnout.
Empty voted_party_cd values exist; label them explicitly when grouping by party."""


@sql_gen_agent.output_validator
async def _validate_sql(ctx: RunContext[SqlDeps], result: Response) -> Response:
    if isinstance(result, InvalidRequest):
        return result
    result.sql_query = result.sql_query.replace("\\", "")
    if not result.sql_query.upper().startswith("SELECT"):
        raise ModelRetry("Please create a SELECT query")
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
        result = await sql_gen_agent.run(question, deps=deps)
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
    """Generate and execute a SQL query against North Carolina voter data.

    Returns results as a markdown table. Use this for direct data questions.
    """
    return await _run_sql_query(question)


_MONTY_TYPE_STUBS = """\
async def run_sql_query(question: str) -> str:
    raise NotImplementedError()
"""


@voter_toolset.tool_plain
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
    settings.VOTER_REG_MODEL,
    defer_model_check=True,
    instructions="""\
You are a voter data analyst. You help users explore North Carolina voter
registration and election history data.

Use run_sql_query for direct data questions. Use run_python_code when you need
to chain multiple queries or compute cross-query statistics.

Present results clearly in markdown. Never expose PII (names, addresses, phone
numbers). Reference voters by ncid only if needed.""",
    toolsets=[voter_toolset],
)
