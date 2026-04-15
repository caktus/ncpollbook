import os

from django.conf import settings


class TestDatabaseSettings:
    def test_conn_max_age_zero_for_asgi(self):
        db = settings.DATABASES["default"]
        assert db["CONN_MAX_AGE"] == 0


class TestCsrfTrustedOrigins:
    def test_empty_by_default(self):
        # In the test environment no env var is set, so the list should be empty.
        assert isinstance(settings.CSRF_TRUSTED_ORIGINS, list)

    def test_parsed_from_env(self, monkeypatch):
        monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://example.com,https://other.com")
        result = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
        assert result == ["https://example.com", "https://other.com"]
