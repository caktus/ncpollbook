from typing import ClassVar

from django.contrib import admin

from apps.ncsbe.models import (
    # MvElections,
    # MvVoterHistory,
    # MvVoterRegistration,
    Voter,
    VoterEvent,
    VoterEventView,
    VoterView,
)


@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = (
        "ncid",
        "county_desc",
        "status_cd",
        "party_cd",
        "gender_code",
        "race_code",
    )
    list_filter = ("status_cd", "party_cd", "gender_code", "race_code", "county_desc")
    search_fields = ("ncid",)
    readonly_fields: ClassVar = [f.name for f in Voter._meta.get_fields()]


@admin.register(VoterEvent)
class VoterEventAdmin(admin.ModelAdmin):
    list_display = (
        "ncid",
        "county_desc",
        "election_lbl",
        "election_desc",
        "voting_method",
        "voted_party_cd",
    )
    list_filter = ("voting_method", "voted_party_cd", "county_desc")
    search_fields = ("ncid",)
    readonly_fields: ClassVar = [f.name for f in VoterEvent._meta.get_fields()]


class ReadOnlyAdmin(admin.ModelAdmin):
    """Base class for read-only admin views (e.g. materialized views)."""

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(VoterView)
class VoterViewAdmin(ReadOnlyAdmin):
    # Avoid COUNT(*) on a large table for every page load
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "ncid",
        "county_name",
        "registration_status_code",
        "registered_party_code",
        "gender_sex_code",
        "race_code",
        "year_of_birth",
        "registration_date",
    )
    # Low-cardinality columns only — avoids expensive DISTINCT queries
    list_filter = (
        "registration_status_code",
        "registered_party_code",
        "gender_sex_code",
        "race_code",
    )

    # Exact-match lookup (= prefix) uses the unique index on ncid
    search_fields = ("=ncid",)
    readonly_fields: ClassVar = [f.name for f in VoterView._meta.get_fields()]


@admin.register(VoterEventView)
class VoterEventViewAdmin(ReadOnlyAdmin):
    show_full_result_count = False
    list_per_page = 50

    list_display = (
        "ncid",
        "voted_county_desc",
        "election_date",
        "election_type",
        "voting_method",
        "voted_party_name",
    )
    list_filter = ("election_type", "election_year", "voting_method")
    # ncid is not indexed on this view — no search_fields to avoid seq scans
    readonly_fields: ClassVar = [f.name for f in VoterEventView._meta.get_fields()]
