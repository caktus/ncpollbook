import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User

from apps.ncsbe.admin import VoterEventViewAdmin, VoterViewAdmin
from apps.ncsbe.models import VoterEventView, VoterView


@pytest.fixture
def site():
    return AdminSite()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def request_factory(superuser, rf):
    request = rf.get("/")
    request.user = superuser
    return request


class TestVoterViewAdmin:
    def test_is_registered(self):
        from django.contrib import admin

        assert admin.site.is_registered(VoterView)

    def test_no_add_permission(self, request_factory, site):
        ma = VoterViewAdmin(VoterView, site)
        assert ma.has_add_permission(request_factory) is False

    def test_no_change_permission(self, request_factory, site):
        ma = VoterViewAdmin(VoterView, site)
        assert ma.has_change_permission(request_factory) is False

    def test_no_delete_permission(self, request_factory, site):
        ma = VoterViewAdmin(VoterView, site)
        assert ma.has_delete_permission(request_factory) is False

    def test_show_full_result_count_disabled(self, site):
        ma = VoterViewAdmin(VoterView, site)
        assert ma.show_full_result_count is False

    def test_search_uses_exact_match(self, site):
        ma = VoterViewAdmin(VoterView, site)
        assert ma.search_fields == ("=ncid",)


class TestVoterEventViewAdmin:
    def test_is_registered(self):
        from django.contrib import admin

        assert admin.site.is_registered(VoterEventView)

    def test_no_add_permission(self, request_factory, site):
        ma = VoterEventViewAdmin(VoterEventView, site)
        assert ma.has_add_permission(request_factory) is False

    def test_no_change_permission(self, request_factory, site):
        ma = VoterEventViewAdmin(VoterEventView, site)
        assert ma.has_change_permission(request_factory) is False

    def test_no_delete_permission(self, request_factory, site):
        ma = VoterEventViewAdmin(VoterEventView, site)
        assert ma.has_delete_permission(request_factory) is False

    def test_show_full_result_count_disabled(self, site):
        ma = VoterEventViewAdmin(VoterEventView, site)
        assert ma.show_full_result_count is False

    def test_no_search_fields(self, site):
        """VoterEventView has no index on ncid — search is intentionally omitted."""
        ma = VoterEventViewAdmin(VoterEventView, site)
        assert not ma.search_fields
