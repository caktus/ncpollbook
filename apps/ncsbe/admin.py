from typing import ClassVar

from django.contrib import admin

from apps.ncsbe.models import (
    # MvElections,
    # MvVoterHistory,
    # MvVoterRegistration,
    Voter,
    VoterEvent,
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


# @admin.register(MvVoterRegistration)
# class MvVoterRegistrationAdmin(admin.ModelAdmin):
#     list_display = (
#         "ncid",
#         "county_desc",
#         "status_cd",
#         "party_cd",
#         "gender_code",
#         "race_code",
#         "age_at_year_end",
#     )
#     list_filter = ("status_cd", "party_cd", "gender_code", "race_code", "county_desc")
#     search_fields = ("ncid",)

#     def has_add_permission(self, request):
#         return False

#     def has_change_permission(self, request, obj=None):
#         return False

#     def has_delete_permission(self, request, obj=None):
#         return False


# @admin.register(MvVoterHistory)
# class MvVoterHistoryAdmin(admin.ModelAdmin):
#     list_display = (
#         "ncid",
#         "county_desc",
#         "election_date",
#         "election_type",
#         "voting_method",
#         "voted_party_cd",
#     )
#     list_filter = ("election_type", "election_year", "voting_method", "voted_party_cd")
#     search_fields = ("ncid",)

#     def has_add_permission(self, request):
#         return False

#     def has_change_permission(self, request, obj=None):
#         return False

#     def has_delete_permission(self, request, obj=None):
#         return False


# @admin.register(MvElections)
# class MvElectionsAdmin(admin.ModelAdmin):
#     list_display = (
#         "election_date",
#         "election_type",
#         "election_year",
#         "election_desc",
#         "total_votes",
#     )
#     list_filter = ("election_type", "election_year")
#     search_fields = ("election_desc",)

#     def has_add_permission(self, request):
#         return False

#     def has_change_permission(self, request, obj=None):
#         return False

#     def has_delete_permission(self, request, obj=None):
#         return False
