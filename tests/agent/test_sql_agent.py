import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import connection
from django.test import override_settings
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.openai import OpenAIChatModel

from apps.agent.models import AgentTool, ModelIdentifier, ToolModel
from apps.agent.sql_agent import (
    InvalidRequest,
    Success,
    _is_safe_select_query,
    _sql_system_prompt,
    _validate_sql,
    _voter_system_prompt,
    generate_csv_export,
    get_tool_model,
    get_view_schema,
    resolve_model,
    run_sql_query,
)
from apps.agent.sql_examples import SQL_EXAMPLES
from apps.ncsbe.models import VoterEventView, VoterView


class TestIsSafeSelectQuery:
    def test_simple_select_is_safe(self):
        assert _is_safe_select_query("SELECT 1") is True

    def test_cte_with_select_is_safe(self):
        sql = "WITH cte AS (SELECT ncid FROM voter_view) SELECT * FROM cte"
        assert _is_safe_select_query(sql) is True

    def test_sql_comment_before_select_is_safe(self):
        sql = "-- count voters\nSELECT COUNT(*) FROM voter_view"
        assert _is_safe_select_query(sql) is True

    def test_no_select_is_not_safe(self):
        assert _is_safe_select_query("SHOW TABLES") is False

    def test_insert_is_not_safe(self):
        assert _is_safe_select_query("INSERT INTO t VALUES (1)") is False

    def test_update_is_not_safe(self):
        assert _is_safe_select_query("UPDATE t SET x=1") is False

    def test_delete_is_not_safe(self):
        assert _is_safe_select_query("DELETE FROM t") is False

    def test_drop_is_not_safe(self):
        assert _is_safe_select_query("DROP TABLE t") is False


class TestGetViewSchema:
    def test_voter_schema_contains_key_fields(self):
        schema = get_view_schema(VoterView)
        assert "ncid" in schema
        assert "registered_party_code" in schema
        assert "registration_status_code" in schema
        assert "county_name" in schema

    def test_voter_event_schema_contains_key_fields(self):
        schema = get_view_schema(VoterEventView)
        assert "election_date" in schema
        assert "election_type" in schema
        assert "voting_method" in schema

    def test_voter_schema_excludes_pii(self):
        schema = get_view_schema(VoterView)
        assert "last_name" not in schema
        assert "first_name" not in schema
        assert "res_street_address" not in schema
        assert "full_phone_number" not in schema

    def test_voter_schema_includes_table_name(self):
        schema = get_view_schema(VoterView)
        assert VoterView._meta.db_table in schema

    def test_voter_event_schema_includes_table_name(self):
        schema = get_view_schema(VoterEventView)
        assert VoterEventView._meta.db_table in schema

    def test_voter_schema_types(self):
        schema = get_view_schema(VoterView)
        # year_of_birth and age_at_end_of_year are SmallIntegerField
        assert "year_of_birth smallint" in schema
        assert "age_at_end_of_year smallint" in schema
        # registration_date is DateField
        assert "registration_date date" in schema

    @pytest.mark.django_db
    def test_get_view_schema_is_valid_sql_structure(self):
        schema = get_view_schema(VoterView)
        assert schema.startswith("CREATE TABLE")
        assert schema.endswith(");")

    def test_voter_schema_includes_db_comments(self):
        schema = get_view_schema(VoterView)
        # Fields with db_comment should appear as inline SQL comments
        assert "-- A=ACTIVE" in schema
        assert "-- Party affiliation:" in schema
        assert "-- County name:" in schema

    def test_voter_event_schema_includes_db_comments(self):
        schema = get_view_schema(VoterEventView)
        assert "-- GENERAL," in schema
        assert "-- ABSENTEE," in schema

    def test_fields_without_db_comment_have_no_comment(self):
        schema = get_view_schema(VoterView)
        # year_of_birth has no db_comment — its line should not contain '--'
        line = next(row for row in schema.splitlines() if "year_of_birth" in row)
        assert "--" not in line


class TestSqlExamples:
    @pytest.mark.django_db
    @pytest.mark.parametrize("sql", SQL_EXAMPLES)
    def test_example_is_syntactically_valid(self, sql):
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN {sql.rstrip(';').rstrip()}")

    def test_example_count(self):
        assert len(SQL_EXAMPLES) == 7


class TestSqlGenSystemPrompt:
    def test_includes_todays_date(self):
        prompt = asyncio.run(_sql_system_prompt())
        assert str(date.today()) in prompt

    def test_never_assume_data_limitations(self):
        prompt = asyncio.run(_sql_system_prompt())
        assert "never return InvalidRequest" in prompt.lower() or "never" in prompt.lower()
        assert "dataset is current" in prompt.lower()

    def test_ncid_is_not_pii(self):
        prompt = asyncio.run(_sql_system_prompt())
        assert "ncid" in prompt.lower()
        assert "not pii" in prompt.lower()


class TestVoterSystemPrompt:
    def test_includes_todays_date(self):
        prompt = _voter_system_prompt()
        assert str(date.today()) in prompt

    def test_includes_run_sql_query_instruction(self):
        prompt = _voter_system_prompt()
        assert "run_sql_query" in prompt

    def test_never_assume_data_limitations(self):
        prompt = _voter_system_prompt()
        assert "dataset is current" in prompt.lower()

    def test_always_include_full_data_table(self):
        prompt = _voter_system_prompt()
        assert "a truncated data table" in prompt

    def test_requires_run_sql_query_for_every_count(self):
        prompt = _voter_system_prompt()
        assert "CRITICAL RULE" in prompt
        assert "EVERY count" in prompt or "every count" in prompt.lower()

    def test_forbids_numbers_from_conversation_history(self):
        prompt = _voter_system_prompt()
        assert "conversation" in prompt.lower()
        assert "never calculate" in prompt.lower() or "never" in prompt.lower()

    def test_ncid_queries_are_allowed(self):
        prompt = _voter_system_prompt()
        assert "ncid" in prompt.lower()
        assert "not pii" in prompt.lower()

    def test_must_present_tool_results_to_user(self):
        prompt = _voter_system_prompt()
        assert "user cannot see tool output" in prompt.lower()
        assert "must present" in prompt.lower() or "you must present" in prompt.lower()

    def test_instructs_to_pass_sql_to_csv_export(self):
        prompt = _voter_system_prompt()
        assert "sql" in prompt.lower() and "generate_csv_export" in prompt

    def test_instructs_to_include_sql_block_in_response(self):
        prompt = _voter_system_prompt()
        assert "```sql" in prompt and "verbatim" in prompt


class TestResolveModel:
    def test_known_prefix_returned_as_string(self):
        assert resolve_model("openai:gpt-4o") == "openai:gpt-4o"

    def test_ollama_prefix_returned_as_string(self):
        assert resolve_model("ollama:llama3.3") == "ollama:llama3.3"

    def test_lmstudio_returns_openai_model(self):
        result = resolve_model("lmstudio:Qwen3-Coder-30B")
        assert isinstance(result, OpenAIChatModel)
        assert result.model_name == "Qwen3-Coder-30B"

    def test_lmstudio_uses_correct_base_url(self):
        result = resolve_model("lmstudio:any-model")
        assert isinstance(result, OpenAIChatModel)
        assert settings.LM_STUDIO_BASE_URL in str(result.client.base_url)

    def test_lmstudio_uses_settings_base_url(self):
        with override_settings(LM_STUDIO_BASE_URL="http://custom-host:5678/v1"):
            result = resolve_model("lmstudio:any-model")
        assert isinstance(result, OpenAIChatModel)
        assert "http://custom-host:5678/v1" in str(result.client.base_url)

    def test_anthropic_prefix_returned_as_string(self):
        assert (
            resolve_model("anthropic:claude-haiku-4-5-20251001")
            == "anthropic:claude-haiku-4-5-20251001"
        )


class TestGetToolModel:
    @pytest.mark.django_db
    def test_raises_when_no_db_records(self):
        with pytest.raises(ValueError, match="No ToolModel configured"):
            async_to_sync(get_tool_model)(AgentTool.SQL_GEN)

    @pytest.mark.django_db
    def test_returns_specific_tool_model_when_configured(self):
        m = ModelIdentifier.objects.create(name="ollama:llama3.3")
        ToolModel.objects.create(tool_name=AgentTool.SQL_GEN, model=m)
        assert async_to_sync(get_tool_model)(AgentTool.SQL_GEN) == "ollama:llama3.3"

    @pytest.mark.django_db
    def test_falls_back_to_default_null_record(self):
        m = ModelIdentifier.objects.create(name="openai:gpt-4o-mini")
        ToolModel.objects.create(tool_name=None, model=m)
        # No sql_gen record — should use the NULL default
        assert async_to_sync(get_tool_model)(AgentTool.SQL_GEN) == "openai:gpt-4o-mini"

    @pytest.mark.django_db
    def test_specific_tool_takes_precedence_over_default(self):
        default_m = ModelIdentifier.objects.create(name="openai:gpt-4o-mini")
        specific_m = ModelIdentifier.objects.create(name="ollama:llama3.3")
        ToolModel.objects.create(tool_name=None, model=default_m)
        ToolModel.objects.create(tool_name=AgentTool.SQL_GEN, model=specific_m)
        assert async_to_sync(get_tool_model)(AgentTool.SQL_GEN) == "ollama:llama3.3"

    @pytest.mark.django_db
    def test_voter_agent_and_sql_gen_can_use_different_models(self):
        sql_m = ModelIdentifier.objects.create(name="bedrock:us.anthropic.claude-sonnet-4-6")
        voter_m = ModelIdentifier.objects.create(name="lmstudio:Qwen3-Coder-30B")
        ToolModel.objects.create(tool_name=AgentTool.SQL_GEN, model=sql_m)
        ToolModel.objects.create(tool_name=AgentTool.VOTER_AGENT, model=voter_m)
        assert (
            async_to_sync(get_tool_model)(AgentTool.SQL_GEN)
            == "bedrock:us.anthropic.claude-sonnet-4-6"
        )
        assert isinstance(async_to_sync(get_tool_model)(AgentTool.VOTER_AGENT), OpenAIChatModel)


class TestValidateSqlRollback:
    def test_rolls_back_on_explain_failure(self):
        """Failed EXPLAIN must rollback so subsequent retries start with a clean transaction."""
        conn = AsyncMock()
        conn.execute.side_effect = psycopg.Error("syntax error")
        ctx = MagicMock()
        ctx.deps.conn = conn
        result = Success(sql_query="SELECT 1")

        with pytest.raises(ModelRetry):
            async_to_sync(_validate_sql)(ctx, result)

        conn.rollback.assert_awaited_once()

    def test_logs_warning_on_invalid_query(self):
        conn = AsyncMock()
        conn.execute.side_effect = psycopg.Error("syntax error")
        ctx = MagicMock()
        ctx.deps.conn = conn
        result = Success(sql_query="SELECT 1")

        with patch("apps.agent.sql_agent.logger") as mock_logger, pytest.raises(ModelRetry):
            async_to_sync(_validate_sql)(ctx, result)

        mock_logger.warning.assert_called_once()
        assert "invalid query" in mock_logger.warning.call_args[0][0]


class TestRunSqlQueryToolErrorHandling:
    def test_returns_error_string_on_exception(self):
        """Tool must return an error string rather than raising, keeping voter_agent alive."""
        with patch(
            "apps.agent.sql_agent._run_sql_query",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = async_to_sync(run_sql_query)("how many voters?")
        assert result.startswith("Error running query:")


class TestGenerateCsvExport:
    def _make_mock_result(self, output):
        result = MagicMock()
        result.output = output
        return result

    def test_returns_artifact_block_on_success(self):
        col = MagicMock()
        col.name = "ncid"
        mock_cur = AsyncMock()
        mock_cur.description = [col]
        mock_cur.fetchall = AsyncMock(return_value=[("ABC123",)])
        mock_cur.__aenter__ = AsyncMock(return_value=mock_cur)
        mock_cur.__aexit__ = AsyncMock(return_value=None)
        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cur)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        success = Success(sql_query="SELECT ncid FROM voter_view LIMIT 1")
        with (
            patch("apps.agent.sql_agent.psycopg.AsyncConnection.connect", return_value=mock_conn),
            patch(
                "apps.agent.sql_agent.sql_gen_agent.run",
                AsyncMock(return_value=self._make_mock_result(success)),
            ),
            patch("apps.agent.sql_agent.get_tool_model", AsyncMock(return_value="openai:gpt-4o")),
        ):
            result = async_to_sync(generate_csv_export)("export active voters")

        assert result.startswith(":::artifact{")
        assert 'type="text/csv"' in result
        assert "ncid" in result
        assert "ABC123" in result
        assert result.endswith(":::")

    def test_returns_error_on_invalid_request(self):
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        invalid = InvalidRequest(error_message="cannot understand question")
        with (
            patch("apps.agent.sql_agent.psycopg.AsyncConnection.connect", return_value=mock_conn),
            patch(
                "apps.agent.sql_agent.sql_gen_agent.run",
                AsyncMock(return_value=self._make_mock_result(invalid)),
            ),
            patch("apps.agent.sql_agent.get_tool_model", AsyncMock(return_value="openai:gpt-4o")),
        ):
            result = async_to_sync(generate_csv_export)("??")

        assert result.startswith("Could not generate export:")
        assert "cannot understand question" in result

    def test_uses_provided_sql_directly(self):
        """When sql is passed, sql_gen_agent is skipped and the SQL is executed directly."""
        col = MagicMock()
        col.name = "county_name"
        mock_cur = AsyncMock()
        mock_cur.description = [col]
        mock_cur.fetchall = AsyncMock(return_value=[("DURHAM",)])
        mock_cur.__aenter__ = AsyncMock(return_value=mock_cur)
        mock_cur.__aexit__ = AsyncMock(return_value=None)
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cur)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        provided_sql = "SELECT county_name FROM voter_view LIMIT 1"
        mock_sql_gen = AsyncMock()
        with (
            patch("apps.agent.sql_agent.psycopg.AsyncConnection.connect", return_value=mock_conn),
            patch("apps.agent.sql_agent.sql_gen_agent.run", mock_sql_gen),
        ):
            result = async_to_sync(generate_csv_export)("export voters", sql=provided_sql)

        mock_sql_gen.assert_not_called()
        assert "county_name" in result
        assert "DURHAM" in result
        assert result.startswith(":::artifact{")

    def test_rejects_unsafe_sql(self):
        """Provided SQL containing write statements is rejected without hitting the DB."""
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)

        with patch("apps.agent.sql_agent.psycopg.AsyncConnection.connect", return_value=mock_conn):
            result = async_to_sync(generate_csv_export)("export", sql="DELETE FROM voter_view")

        assert "not a safe SELECT query" in result
