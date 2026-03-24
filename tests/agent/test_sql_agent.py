import pytest

from apps.agent.sql_agent import get_view_schema
from apps.ncsbe.models import VoterEventView, VoterView


class TestGetViewSchema:
    def test_voter_schema_contains_key_fields(self):
        schema = get_view_schema(VoterView)
        assert "ncid" in schema
        assert "party_cd" in schema
        assert "status_cd" in schema
        assert "county_desc" in schema

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
        # birth_year and age_at_year_end are SmallIntegerField
        assert "birth_year smallint" in schema
        assert "age_at_year_end smallint" in schema
        # registr_dt is DateField
        assert "registr_dt date" in schema

    @pytest.mark.django_db
    def test_get_view_schema_is_valid_sql_structure(self):
        schema = get_view_schema(VoterView)
        assert schema.startswith("CREATE TABLE")
        assert schema.endswith(");")
