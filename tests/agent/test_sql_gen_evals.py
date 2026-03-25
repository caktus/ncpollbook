"""Evals for the SQL generation agent (sql_gen_agent) and voter_agent.

sql_gen_agent evals:
- Generates valid SELECT queries for voter data questions
- Returns InvalidRequest for off-topic questions
- Avoids PII column references in SQL

voter_agent evals:
- Always returns a non-empty string
- Response does not expose PII
- Data responses include a SQL code block
"""

from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from apps.agent.sql_agent import InvalidRequest, Response, Success

# ---------------------------------------------------------------------------
# Custom evaluators
# ---------------------------------------------------------------------------


@dataclass
class IsSelectQuery(Evaluator):
    """Assert the output is a Success containing a SELECT SQL query."""

    def evaluate(self, ctx: EvaluatorContext) -> dict[str, bool]:
        is_success = isinstance(ctx.output, Success)
        return {
            "is_success": is_success,
            "is_select": is_success and ctx.output.sql_query.upper().startswith("SELECT"),
        }


@dataclass
class IsInvalidRequest(Evaluator):
    """Assert the output is an InvalidRequest (e.g. off-topic question)."""

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        return isinstance(ctx.output, InvalidRequest)


@dataclass
class NoPiiColumns(Evaluator):
    """Assert the generated SQL does not reference known PII column names."""

    _PII = frozenset({"last_name", "first_name", "res_street_address", "full_phone_number"})

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        if not isinstance(ctx.output, Success):
            return True  # not applicable
        sql = ctx.output.sql_query.lower()
        return not any(col in sql for col in self._PII)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

sql_gen_dataset: Dataset[str, Response, None] = Dataset(
    name="sql_gen_agent",
    evaluators=[NoPiiColumns()],
    cases=[
        Case(
            name="count_active_voters",
            inputs="How many active voters are there?",
            evaluators=[IsSelectQuery()],
        ),
        Case(
            name="voters_by_party",
            inputs="Show voter counts grouped by party",
            evaluators=[IsSelectQuery()],
        ),
        Case(
            name="off_topic_weather",
            inputs="What's the weather like today?",
            evaluators=[IsInvalidRequest()],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _simulated_task(question: str) -> Response:
    """Simulate sql_gen_agent responses for deterministic eval testing."""
    q = question.lower()
    if any(w in q for w in ("voter", "party", "election", "county")):
        return Success(
            sql_query="SELECT COUNT(*) FROM voter_view WHERE status_cd = 'A'",
            explanation="",
        )
    return InvalidRequest(error_message="Not a voter data question")


class TestSqlGenEvals:
    def test_dataset_with_simulated_responses(self):
        """Run the eval dataset against a simulated task function."""
        report = sql_gen_dataset.evaluate_sync(_simulated_task)
        assert len(report.failures) == 0
        for case in report.cases:
            for name, result in case.assertions.items():
                assert result.value, f"Assertion '{name}' failed for case '{case.name}'"

    def test_is_select_query_evaluator(self):
        """Unit-test IsSelectQuery evaluator with a known good output."""
        ds: Dataset[str, Response, None] = Dataset(
            cases=[Case(inputs="q")],
            evaluators=[IsSelectQuery()],
        )
        report = ds.evaluate_sync(lambda _: Success(sql_query="SELECT 1", explanation=""))
        case = report.cases[0]
        assert case.assertions["is_success"].value is True
        assert case.assertions["is_select"].value is True

    def test_no_pii_evaluator_detects_pii(self):
        """NoPiiColumns evaluator should flag SQL containing PII column names."""
        ds: Dataset[str, Response, None] = Dataset(
            cases=[Case(inputs="q")],
            evaluators=[NoPiiColumns()],
        )
        report = ds.evaluate_sync(
            lambda _: Success(sql_query="SELECT last_name FROM voter_view", explanation="")
        )
        assert report.cases[0].assertions["NoPiiColumns"].value is False


# ---------------------------------------------------------------------------
# voter_agent evaluators
# ---------------------------------------------------------------------------


@dataclass
class HasSqlCodeBlock(Evaluator):
    """Assert the voter_agent response contains a fenced SQL code block."""

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        return "```sql" in ctx.output


@dataclass
class NoPiiInResponse(Evaluator):
    """Assert the voter_agent response does not expose known PII patterns."""

    _PII = frozenset({"last_name", "first_name", "res_street_address", "full_phone_number"})

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        text = ctx.output.lower()
        return not any(col in text for col in self._PII)


# ---------------------------------------------------------------------------
# voter_agent dataset
# ---------------------------------------------------------------------------

_SQL_RESPONSE = "```sql\nSELECT COUNT(*) FROM voter_view\n```\n\n| count |\n| --- |\n| 100 |"
_TEXT_RESPONSE = "I can only answer questions about North Carolina voter data."

voter_agent_dataset: Dataset[str, str, None] = Dataset(
    name="voter_agent",
    evaluators=[NoPiiInResponse()],
    cases=[
        Case(
            name="data_question",
            inputs="How many active voters are there?",
            evaluators=[HasSqlCodeBlock()],
        ),
        Case(
            name="off_topic",
            inputs="What is the capital of France?",
        ),
    ],
)


def _simulated_voter_task(question: str) -> str:
    """Simulate voter_agent responses for deterministic eval testing."""
    if any(w in question.lower() for w in ("voter", "party", "election", "county")):
        return _SQL_RESPONSE
    return _TEXT_RESPONSE


class TestVoterAgentEvals:
    def test_dataset_with_simulated_responses(self):
        """Run the voter_agent eval dataset against a simulated task."""
        report = voter_agent_dataset.evaluate_sync(_simulated_voter_task)
        assert len(report.failures) == 0
        for case in report.cases:
            for name, result in case.assertions.items():
                assert result.value, f"Assertion '{name}' failed for case '{case.name}'"

    def test_has_sql_code_block_evaluator(self):
        """HasSqlCodeBlock passes when output contains ```sql and fails otherwise."""
        ds: Dataset[str, str, None] = Dataset(
            cases=[Case(inputs="q")],
            evaluators=[HasSqlCodeBlock()],
        )
        report_pass = ds.evaluate_sync(lambda _: _SQL_RESPONSE)
        assert report_pass.cases[0].assertions["HasSqlCodeBlock"].value is True

        report_fail = ds.evaluate_sync(lambda _: _TEXT_RESPONSE)
        assert report_fail.cases[0].assertions["HasSqlCodeBlock"].value is False

    def test_no_pii_in_response_evaluator(self):
        """NoPiiInResponse flags responses containing PII column names."""
        ds: Dataset[str, str, None] = Dataset(
            cases=[Case(inputs="q")],
            evaluators=[NoPiiInResponse()],
        )
        report = ds.evaluate_sync(lambda _: "The voter last_name is Smith")
        assert report.cases[0].assertions["NoPiiInResponse"].value is False
