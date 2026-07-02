import pytest
from django.core.cache import cache

from apps.agent.models import ModelIdentifier, ToolModel
from apps.ncsbe.forms import CountyForm, VoterHistoryForm
from apps.ncsbe.models import VoterEventView, VoterView
from tests.ncsbe.factories import VoterEventFactory, VoterFactory


class TestCountyForm:
    def test_clean_county_name_uppercases(self):
        form = CountyForm({"county_name": "durham"})
        assert form.is_valid()
        assert form.cleaned_data["county_name"] == "DURHAM"

    def test_invalid_county_raises_validation_error(self):
        form = CountyForm({"county_name": "FAKE_COUNTY"})
        assert not form.is_valid()
        assert "county_name" in form.errors

    def test_new_hanover_with_space_is_valid(self):
        # Map click generates "NEW HANOVER"; COUNTY_ID_MAP must accept it.
        form = CountyForm({"county_name": "NEW HANOVER"})
        assert form.is_valid()
        assert form.cleaned_data["county_name"] == "NEW HANOVER"

    def test_newhanover_no_space_is_invalid(self):
        # Old key "NEWHANOVER" no longer exists; map/DB use "NEW HANOVER".
        form = CountyForm({"county_name": "NEWHANOVER"})
        assert not form.is_valid()


class TestVoterHistoryForm:
    def test_clean_ncid_strips_and_uppercases(self):
        form = VoterHistoryForm({"ncid": "  aa000001  "})
        assert form.is_valid()
        assert form.cleaned_data["ncid"] == "AA000001"


@pytest.mark.django_db
class TestHomeView:
    def test_get_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_county_search_redirects(self, client):
        response = client.get("/?county_name=durham")
        assert response.status_code == 302
        assert response["Location"] == "/county/DURHAM/"

    def test_invalid_county_shows_form_errors(self, client):
        response = client.get("/?county_name=INVALID")
        assert response.status_code == 200

    def test_counties_context_for_datalist(self, client):
        response = client.get("/")
        assert "DURHAM" in response.context["counties"]
        assert "WAKE" in response.context["counties"]

    def test_summary_counts_in_context(self, client):
        response = client.get("/")
        assert "voter_count" in response.context
        assert "event_count" in response.context

    def test_summary_counts_are_cached(self, client, settings):
        settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        cache.clear()
        client.get("/")
        assert cache.get("home_voter_count") is not None
        assert cache.get("home_event_count") is not None

    def test_chatbot_url_in_context(self, client, settings):
        settings.CHATBOT_URL = "https://chat.example.com"
        response = client.get("/")
        assert response.context["chatbot_url"] == "https://chat.example.com"

    def test_tool_models_in_context(self, client):
        model = ModelIdentifier.objects.create(name="test:model-1", deployment_type="cloud-api")
        ToolModel.objects.create(tool_name="voter_agent", model=model)
        response = client.get("/")
        assert len(response.context["tool_models"]) == 1
        assert response.context["tool_models"][0].model.name == "test:model-1"

    def test_default_tool_model_excluded_from_context(self, client):
        model = ModelIdentifier.objects.create(name="test:default", deployment_type="cloud-api")
        ToolModel.objects.create(tool_name=None, model=model)
        response = client.get("/")
        assert len(response.context["tool_models"]) == 0


@pytest.mark.django_db
class TestCountyRegistrationsView:
    def test_invalid_county_returns_404(self, client):
        response = client.get("/county/FAKE/")
        assert response.status_code == 404

    def test_county_case_insensitive(self, client):
        response = client.get("/county/durham/")
        assert response.status_code == 200

    def test_aggregate_counts(self, client):
        VoterFactory(county_desc="DURHAM", status_cd="A", gender_code="F")
        VoterFactory(county_desc="DURHAM", status_cd="A", gender_code="M")
        VoterFactory(county_desc="DURHAM", status_cd="I", gender_code="F")
        VoterFactory(county_desc="DURHAM", status_cd="A", race_code="P", gender_code="U")
        VoterView.refresh()
        response = client.get("/county/DURHAM/")
        assert response.status_code == 200
        stats = response.context["stats"]
        assert stats["total"] == 3  # only active
        assert stats["female"] == 1  # inactive voter excluded from gender breakdown
        assert stats["male"] == 1
        assert stats["pacific_islander"] == 1

    def test_sample_voters_up_to_25(self, client):
        for _ in range(30):
            VoterFactory(county_desc="DURHAM")
        VoterView.refresh()
        response = client.get("/county/DURHAM/")
        assert response.status_code == 200
        assert len(response.context["sample_voters"]) == 25

    def test_precinct_stats_in_context(self, client):
        VoterFactory(
            county_desc="DURHAM",
            status_cd="A",
            precinct_abbrv="01",
            precinct_desc="PRECINCT 01",
            race_code="B",
            ethnic_code="NL",
        )
        VoterFactory(
            county_desc="DURHAM",
            status_cd="A",
            precinct_abbrv="01",
            precinct_desc="PRECINCT 01",
            race_code="W",
            ethnic_code="HL",
        )
        VoterFactory(
            county_desc="DURHAM",
            status_cd="A",
            precinct_abbrv="02",
            precinct_desc="PRECINCT 02",
            race_code="A",
            ethnic_code="NL",
        )
        VoterFactory(
            county_desc="DURHAM", status_cd="I", precinct_abbrv="01", precinct_desc="PRECINCT 01"
        )
        VoterView.refresh()
        response = client.get("/county/DURHAM/")
        assert response.status_code == 200
        precinct_stats = response.context["precinct_stats"]
        assert len(precinct_stats) == 2
        # sorted by active_voters descending
        p1 = precinct_stats[0]
        assert p1["precinct_desc"] == "PRECINCT 01"
        assert p1["active_voters"] == 2
        assert p1["pct_black"] == 50  # 1 of 2
        assert p1["pct_white"] == 50  # 1 of 2
        assert p1["pct_hispanic"] == 50  # 1 of 2 (HL ethnicity)
        assert precinct_stats[1]["precinct_desc"] == "PRECINCT 02"
        assert precinct_stats[1]["pct_asian"] == 100

    def test_precinct_stats_excludes_inactive_voters(self, client):
        VoterFactory(
            county_desc="DURHAM", status_cd="I", precinct_abbrv="01", precinct_desc="PRECINCT 01"
        )
        VoterView.refresh()
        response = client.get("/county/DURHAM/")
        assert list(response.context["precinct_stats"]) == []


@pytest.mark.django_db
class TestVoterHistoryView:
    def test_unknown_ncid_returns_200_with_empty_events(self, client):
        VoterEventView.refresh()
        response = client.get("/voter/XXXXXXXX/")
        assert response.status_code == 200
        assert response.context["events"] == []

    def test_no_events_returns_200_with_empty_list(self, client):
        VoterFactory(ncid="AA000001")
        VoterView.refresh()
        VoterEventView.refresh()
        response = client.get("/voter/AA000001/")
        assert response.status_code == 200
        assert response.context["events"] == []

    def test_voter_history_returns_200(self, client):
        event = VoterEventFactory(ncid="AA000099")
        VoterEventView.refresh()
        response = client.get(f"/voter/{event.ncid}/")
        assert response.status_code == 200
        assert response.context["ncid"] == "AA000099"

    def test_events_ordered_by_date_desc(self, client):
        VoterEventFactory(ncid="BB000001", election_lbl="11/05/2024")
        VoterEventFactory(ncid="BB000001", election_lbl="03/05/2024")
        VoterEventView.refresh()
        response = client.get("/voter/BB000001/")
        events = list(response.context["events"])
        assert events[0].election_date > events[1].election_date

    def test_demographics_in_context(self, client):
        VoterFactory(ncid="CC000001", county_desc="WAKE", precinct_desc="PRECINCT 05")
        VoterView.refresh()
        VoterEventView.refresh()
        response = client.get("/voter/CC000001/")
        assert response.status_code == 200
        assert response.context["voter"].county_name == "WAKE"
        assert response.context["voter"].precinct_desc == "PRECINCT 05"

    def test_precinct_shown_on_events(self, client):
        VoterEventFactory(ncid="DD000001", pct_description="PRECINCT 03")
        VoterEventView.refresh()
        response = client.get("/voter/DD000001/")
        assert response.context["events"][0].pct_description == "PRECINCT 03"
