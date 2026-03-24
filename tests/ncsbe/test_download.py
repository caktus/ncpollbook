import datetime
import os

from apps.ncsbe.etl.download import is_fresh


class TestIsFresh:
    def test_missing_file_is_not_fresh(self, tmp_path):
        assert is_fresh(tmp_path / "missing.zip") is False

    def test_new_file_is_fresh(self, tmp_path):
        f = tmp_path / "data.zip"
        f.write_bytes(b"")
        assert is_fresh(f) is True

    def test_old_file_is_not_fresh(self, tmp_path):
        f = tmp_path / "data.zip"
        f.write_bytes(b"")
        old_time = (datetime.datetime.now() - datetime.timedelta(days=8)).timestamp()
        os.utime(f, (old_time, old_time))
        assert is_fresh(f) is False
