from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest
from asgiref.sync import async_to_sync
from django.db import connection
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.openai import OpenAIChatModel

from apps.agent.models import AgentTool, ModelIdentifier, ToolModel
from apps.agent.sql_agent import (
    _LM_STUDIO_BASE_URL,
    Success,
    _is_safe_select_query,
    _validate_sql,
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
        assert _LM_STUDIO_BASE_URL in str(result.client.base_url)


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


class TestRunSqlQueryToolErrorHandling:
    def test_returns_error_string_on_exception(self):
        """Tool must return an error string rather than raising, keeping voter_agent alive."""
        with patch(
            "apps.agent.sql_agent._run_sql_query",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = async_to_sync(run_sql_query)("how many voters?")
        assert result.startswith("Error running query:")
