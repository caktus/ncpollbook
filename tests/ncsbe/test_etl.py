"""
End-to-end ETL integration tests.

Builds minimal TSV fixtures from factory instances, loads them into the
database via the same code path as production, refreshes the materialized
views, and asserts the expected rows appear.  No HTTP downloads or mocking.
"""

from pathlib import Path

import pytest

from apps.ncsbe.constants import HISTORY_HEADER_COLUMNS, VOTER_HEADER_COLUMNS
from apps.ncsbe.etl.loader import load_history_file, load_voter_file
from apps.ncsbe.models import Voter, VoterEvent, VoterEventView, VoterView
from tests.ncsbe.factories import VoterEventFactory, VoterFactory

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _voter_tsv_row(voter: Voter) -> str:
    """Serialize a Voter instance to a tab-separated row matching the source file layout."""
    return "\t".join(f'"{getattr(voter, col, "")}"' for col in VOTER_HEADER_COLUMNS)


def _history_tsv_row(event: VoterEvent) -> str:
    """Serialize a VoterEvent instance to a tab-separated row matching the source file layout."""
    return "\t".join(f'"{getattr(event, col, "")}"' for col in HISTORY_HEADER_COLUMNS)


def _build_voter_txt(path: Path, voters: list[Voter]) -> None:
    header = "\t".join(f'"{col}"' for col in VOTER_HEADER_COLUMNS)
    rows = [_voter_tsv_row(v) for v in voters]
    path.write_text("\n".join([header, *rows]), encoding="utf-8")


def _build_history_txt(path: Path, events: list[VoterEvent]) -> None:
    header = "\t".join(f'"{col}"' for col in HISTORY_HEADER_COLUMNS)
    rows = [_history_tsv_row(e) for e in events]
    path.write_text("\n".join([header, *rows]), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestFullEtl:
    def test_voter_rows_appear_in_view(self, tmp_path):
        voters = [
            VoterFactory.build(ncid="AA000001", status_cd="A"),
            VoterFactory.build(ncid="AA000002", status_cd="I"),
            VoterFactory.build(ncid="AA000003", status_cd="R"),
        ]
        voter_txt = tmp_path / "ncvoter_Statewide.txt"
        _build_voter_txt(voter_txt, voters)

        count = load_voter_file(voter_txt)
        assert count == 3

        VoterView.refresh(concurrently=False)
        assert VoterView.objects.count() == 3
        ncids = set(VoterView.objects.values_list("ncid", flat=True))
        assert ncids == {"AA000001", "AA000002", "AA000003"}

    def test_history_rows_appear_in_view(self, tmp_path):
        voter_txt = tmp_path / "ncvoter_Statewide.txt"
        _build_voter_txt(voter_txt, [VoterFactory.build(ncid="AA000010")])
        load_voter_file(voter_txt)

        history_txt = tmp_path / "ncvhis_Statewide.txt"
        _build_history_txt(
            history_txt,
            [
                VoterEventFactory.build(
                    ncid="AA000010", election_lbl="11/05/2024", election_desc="11/05/2024 GENERAL"
                ),
                VoterEventFactory.build(
                    ncid="AA000010", election_lbl="05/17/2022", election_desc="05/17/2022 PRIMARY"
                ),
            ],
        )

        count = load_history_file(history_txt)
        assert count == 2

        VoterEventView.refresh(concurrently=False)
        events = VoterEventView.objects.filter(ncid="AA000010").order_by("election_date")
        assert events.count() == 2
        assert events[0].election_type == "PRIMARY"
        assert events[1].election_type == "GENERAL"

    def test_voter_view_registr_dt_cast(self, tmp_path):
        voter_txt = tmp_path / "ncvoter_Statewide.txt"
        _build_voter_txt(
            voter_txt,
            [
                VoterFactory.build(ncid="AA000020", registr_dt="03/15/2005"),
                VoterFactory.build(ncid="AA000021", registr_dt="xx/xx/xxxx"),  # masked → NULL
            ],
        )
        load_voter_file(voter_txt)
        VoterView.refresh(concurrently=False)

        v = VoterView.objects.get(ncid="AA000020")
        assert str(v.registration_date) == "2005-03-15"
        assert v.registration_year == 2005

        v2 = VoterView.objects.get(ncid="AA000021")
        assert v2.registration_date is None
