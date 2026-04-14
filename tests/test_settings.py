from django.conf import settings


class TestDatabaseSettings:
    def test_pool_options_configured(self):
        db = settings.DATABASES["default"]
        assert db["CONN_MAX_AGE"] == 0
        pool = db["OPTIONS"]["pool"]
        assert "min_size" in pool
        assert "max_size" in pool
        assert pool["min_size"] <= pool["max_size"]
