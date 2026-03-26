import pytest
from django.conf import settings
from django.db import connection

from apps.agent.sql_agent import get_view_schema
from apps.agent.sql_examples import SQL_EXAMPLES
from apps.ncsbe.models import VoterEventView, VoterView


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


class TestSettings:
    def test_voter_reg_models_contains_primary_model(self):
        assert settings.VOTER_REG_MODEL in settings.VOTER_REG_MODELS

    def test_voter_reg_models_is_list(self):
        assert isinstance(settings.VOTER_REG_MODELS, list)
        assert len(settings.VOTER_REG_MODELS) >= 1

    def test_voter_reg_model_derived_from_models_list(self, monkeypatch):
        # When only VOTER_REG_MODELS is set, VOTER_REG_MODEL should pick the first entry.
        monkeypatch.setenv("VOTER_REG_MODELS", "ollama:llama3.3,ollama:mistral")
        monkeypatch.delenv("VOTER_REG_MODEL", raising=False)
        from importlib import reload

        import config.settings as s

        reload(s)
        assert s.VOTER_REG_MODEL == "ollama:llama3.3"
        assert s.VOTER_REG_MODELS == ["ollama:llama3.3", "ollama:mistral"]
