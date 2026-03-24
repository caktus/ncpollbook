import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Ensure materialized views are created after the test database is set up."""
    with django_db_blocker.unblock():
        call_command("sync_pgviews", "--force")
