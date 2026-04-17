import pytest

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
        VoterView.refresh()
        response = client.get("/county/DURHAM/")
        assert response.status_code == 200
        stats = response.context["stats"]
        assert stats["total"] == 2  # only active
        assert stats["female"] == 1  # inactive voter excluded from gender breakdown
        assert stats["male"] == 1

    def test_sample_voters_shown(self, client):
        VoterFactory(county_desc="DURHAM")
        VoterView.refresh()
        response = client.get("/county/DURHAM/")
        assert response.status_code == 200
        assert len(response.context["sample_voters"]) == 1


@pytest.mark.django_db
class TestVoterHistoryView:
    def test_unknown_ncid_returns_404(self, client):
        VoterEventView.refresh()
        response = client.get("/voter/XXXXXXXX/")
        assert response.status_code == 404

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
