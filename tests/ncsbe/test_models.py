import pytest

from apps.ncsbe.models import VoterEventView, VoterView
from tests.ncsbe.factories import VoterEventFactory, VoterFactory


@pytest.mark.django_db
class TestVoterView:
    def test_includes_all_statuses(self):
        VoterFactory(status_cd="A")
        VoterFactory(status_cd="I")
        VoterFactory(status_cd="R")
        VoterView.refresh()
        assert VoterView.objects.count() == 3

    def test_str(self):
        VoterFactory(ncid="AA000001")
        VoterView.refresh()
        voter = VoterView.objects.get(ncid="AA000001")
        assert str(voter) == "AA000001"


@pytest.mark.django_db
class TestVoterEventView:
    def test_election_type_derived(self):
        VoterEventFactory(election_lbl="11/05/2024", election_desc="11/05/2024 GENERAL")
        VoterEventView.refresh()
        event = VoterEventView.objects.first()
        assert event.election_type == "GENERAL"
