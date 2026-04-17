import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Ensure materialized views are created after the test database is set up."""
    with django_db_blocker.unblock():
        call_command("sync_pgviews", "--force")


@pytest.fixture(autouse=True)
def disable_cache(settings):
    """Use dummy cache in all tests so @cache_page doesn't obscure response.context."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
