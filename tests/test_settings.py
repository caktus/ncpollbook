from django.conf import settings


class TestDatabaseSettings:
    def test_conn_max_age_zero_for_asgi(self):
        db = settings.DATABASES["default"]
        assert db["CONN_MAX_AGE"] == 0
