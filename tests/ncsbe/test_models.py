import pytest

from apps.ncsbe.models import Voter, VoterEvent
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
