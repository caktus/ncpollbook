import pytest

from apps.ncsbe.models import Voter, VoterEvent, VoterEventView, VoterView
from tests.ncsbe.factories import VoterEventFactory, VoterFactory


@pytest.mark.django_db
class TestVoter:
    def test_str(self):
        voter = VoterFactory(ncid="AA123456", county_desc="DURHAM")
        assert str(voter) == "AA123456 (DURHAM)"

    def test_db_table(self):
        assert Voter._meta.db_table == "ncsbe_voter"

    def test_create(self):
        voter = VoterFactory(status_cd="A", party_cd="DEM")
        assert voter.pk is not None
        assert voter.status_cd == "A"
        assert voter.party_cd == "DEM"


@pytest.mark.django_db
class TestVoterEvent:
    def test_str(self):
        event = VoterEventFactory(ncid="AA123456", election_lbl="11/05/2024")
        assert str(event) == "AA123456 — 11/05/2024"

    def test_db_table(self):
        assert VoterEvent._meta.db_table == "ncsbe_voterevent"

    def test_create(self):
        event = VoterEventFactory(voting_method="EARLY VOTING IN-PERSON")
        assert event.pk is not None
        assert event.voting_method == "EARLY VOTING IN-PERSON"


@pytest.mark.django_db
class TestVoterView:
    def test_db_table(self):
        assert VoterView._meta.db_table == "ncsbe_voterview"

    def test_includes_all_statuses(self):
        VoterFactory(status_cd="A")
        VoterFactory(status_cd="I")
        VoterFactory(status_cd="R")  # removed — previously excluded
        VoterView.refresh(concurrently=False)
        assert VoterView.objects.count() == 3

    def test_str(self):
        VoterFactory(ncid="AA000001")
        VoterView.refresh(concurrently=False)
        voter = VoterView.objects.get(ncid="AA000001")
        assert str(voter) == "AA000001"


@pytest.mark.django_db
class TestVoterEventView:
    def test_db_table(self):
        assert VoterEventView._meta.db_table == "ncsbe_votereventview"

    def test_str(self):
        VoterEventFactory(ncid="AA000001", election_lbl="11/05/2024")
        VoterEventView.refresh(concurrently=False)
        event = VoterEventView.objects.first()
        assert str(event) == "AA000001 — 2024-11-05"

    def test_election_type_derived(self):
        VoterEventFactory(election_lbl="11/05/2024", election_desc="11/05/2024 GENERAL")
        VoterEventView.refresh(concurrently=False)
        event = VoterEventView.objects.first()
        assert event.election_type == "GENERAL"
