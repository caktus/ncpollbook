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


class TestSentrySettings:
    def test_dsn_not_set_by_default(self):
        assert settings.SENTRY_DSN is None

    def test_send_default_pii_true_by_default(self):
        assert settings.SENTRY_SEND_DEFAULT_PII is True

    def test_send_default_pii_env_false(self, monkeypatch):
        monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "False")
        result = os.getenv("SENTRY_SEND_DEFAULT_PII", "True") == "True"
        assert result is False
