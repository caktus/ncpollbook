from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from django.core.management import load_command_class

from apps.ncsbe.etl.loader import elapsed_timer, load_history_file, load_voter_file
from apps.ncsbe.management.commands.ncsbe import _distinct_values, peek_file
from apps.ncsbe.models import VoterView
from tests.ncsbe.factories import VoterFactory


class TestPeekFile:
    def _write_tsv(self, tmp_path, rows: list[str]) -> object:
        f = tmp_path / "test.txt"
        f.write_text("\n".join(rows), encoding="utf-8")
        return f

    def test_returns_column_names(self, tmp_path):
        f = self._write_tsv(tmp_path, ['"col_a"\t"col_b"', '"x"\t"1"'])
        result = peek_file(f)
        cols = [r[0] for r in result]
        assert cols == ["col_a", "col_b"]

    def test_returns_dtype_and_samples(self, tmp_path):
        f = self._write_tsv(tmp_path, ['"name"\t"age"', '"Alice"\t"30"', '"Bob"\t"25"'])
        result = peek_file(f)
        name_col = next(r for r in result if r[0] == "name")
        assert "Alice" in name_col[2]

    def test_n_rows_limits_sample(self, tmp_path):
        rows = ['"val"'] + [f'"{i}"' for i in range(50)]
        f = self._write_tsv(tmp_path, rows)
        result = peek_file(f, n_rows=5)
        # samples are capped at 3 regardless
        assert len(result[0][2]) <= 3


class TestElapsedTimer:
    def test_records_elapsed(self):
        with elapsed_timer() as t:
            pass
        assert t[0] >= 0

    def test_elapsed_increases_with_time(self):
        import time

        with elapsed_timer() as t:
            time.sleep(0.01)
        assert t[0] >= 0.01


class TestLoadTiming:
    def _make_mock_loader(self, row_count: int):
        """Return a mock that patches DB internals and returns row_count."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = (row_count,)
        mock_cur.copy.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_cur.copy.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_load_voter_file_returns_count(self, tmp_path):
        tsv = tmp_path / "ncvoter.txt"
        tsv.write_text("header\n", encoding="utf-8")
        mock_conn = self._make_mock_loader(42)
        with patch("apps.ncsbe.etl.loader._get_psycopg_conn", return_value=mock_conn):
            count = load_voter_file(tsv)
        assert count == 42

    def test_load_history_file_returns_count(self, tmp_path):
        tsv = tmp_path / "ncvhis.txt"
        tsv.write_text("header\n", encoding="utf-8")
        mock_conn = self._make_mock_loader(99)
        with patch("apps.ncsbe.etl.loader._get_psycopg_conn", return_value=mock_conn):
            count = load_history_file(tsv)
        assert count == 99


@pytest.mark.django_db
class TestDistinctValues:
    def test_lists_distinct_values(self):
        VoterFactory(status_cd="A")
        VoterFactory(status_cd="I")
        VoterView.refresh()
        result = _distinct_values(VoterView, "registration_status_code", max_values=20)
        assert "A" in result
        assert "I" in result
        assert ", " in result

    def test_truncates_when_over_max(self):
        for i in range(5):
            VoterFactory(party_cd=f"P{i}")
        VoterView.refresh()
        result = _distinct_values(VoterView, "registered_party_code", max_values=3)
        assert "distinct" in result
        assert "..." in result


@pytest.mark.django_db
class TestCommentsCommand:
    def test_outputs_column_names_for_both_views(self):
        VoterFactory()
        VoterView.refresh()
        cmd = load_command_class("apps.ncsbe", "ncsbe")
        result = CliRunner().invoke(cmd, ["comments"])
        assert result.exit_code == 0, result.output
        assert "VoterView" in result.output
        assert "VoterEventView" in result.output
        assert "registration_status_code" in result.output
        assert "election_type" in result.output
