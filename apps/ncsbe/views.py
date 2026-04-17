from django.conf import settings
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page

from apps.ncsbe.constants import (
    COUNTY_ID_MAP,
    EthnicCode,
    GenderCode,
    PartyCode,
    RaceCode,
    StatusCode,
)
from apps.ncsbe.forms import CountyForm, VoterHistoryForm
from apps.ncsbe.models import VoterEventView, VoterView

CACHE_TTL = 60 * 60  # 1 hour


@cache_page(CACHE_TTL)
def home(request: HttpRequest) -> HttpResponse:
    counties = sorted(COUNTY_ID_MAP.keys())
    if request.method == "GET" and "county_name" in request.GET:
        form = CountyForm(request.GET)
        if form.is_valid():
            return redirect("county_registrations", county_name=form.cleaned_data["county_name"])
    else:
        form = CountyForm()
    voter_count = VoterView.objects.count()
    event_count = VoterEventView.objects.count()
    return render(
        request,
        "ncsbe/home.html",
        {
            "form": form,
            "counties": counties,
            "voter_count": voter_count,
            "event_count": event_count,
            "chatbot_url": getattr(settings, "CHATBOT_URL", ""),
        },
    )


@cache_page(CACHE_TTL)
def county_registrations(request: HttpRequest, county_name: str) -> HttpResponse:
    form = CountyForm({"county_name": county_name})
    if not form.is_valid():
        raise Http404("County not found.")
    county_name = form.cleaned_data["county_name"]

    qs = VoterView.objects.filter(county_name=county_name)
    stats = qs.aggregate(
        total=Count("ncid", filter=Q(registration_status_code="A")),
        # Gender (active only)
        female=Count(
            "ncid", filter=Q(registration_status_code="A", gender_sex_code=GenderCode.FEMALE)
        ),
        male=Count("ncid", filter=Q(registration_status_code="A", gender_sex_code=GenderCode.MALE)),
        gender_u=Count(
            "ncid", filter=Q(registration_status_code="A", gender_sex_code=GenderCode.UNDESIGNATED)
        ),
        # Party (active only)
        dem=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.DEMOCRATIC),
        ),
        rep=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.REPUBLICAN),
        ),
        una=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.UNAFFILIATED),
        ),
        lib=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.LIBERTARIAN),
        ),
        gre=Count(
            "ncid", filter=Q(registration_status_code="A", registered_party_code=PartyCode.GREEN)
        ),
        cst=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.CONSTITUTION),
        ),
        nlb=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.NO_LABELS),
        ),
        jfa=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.JUSTICE_FOR_ALL),
        ),
        wtp=Count(
            "ncid",
            filter=Q(registration_status_code="A", registered_party_code=PartyCode.WE_THE_PEOPLE),
        ),
        # Race — active only; Pacific Islander omitted per spec
        white=Count("ncid", filter=Q(registration_status_code="A", race_code=RaceCode.WHITE)),
        black=Count("ncid", filter=Q(registration_status_code="A", race_code=RaceCode.BLACK)),
        asian=Count("ncid", filter=Q(registration_status_code="A", race_code=RaceCode.ASIAN)),
        american_indian=Count(
            "ncid", filter=Q(registration_status_code="A", race_code=RaceCode.AMERICAN_INDIAN)
        ),
        two_or_more=Count(
            "ncid", filter=Q(registration_status_code="A", race_code=RaceCode.TWO_OR_MORE)
        ),
        other_race=Count("ncid", filter=Q(registration_status_code="A", race_code=RaceCode.OTHER)),
        race_u=Count(
            "ncid", filter=Q(registration_status_code="A", race_code=RaceCode.UNDESIGNATED)
        ),
        # Ethnicity (active only)
        hispanic=Count(
            "ncid", filter=Q(registration_status_code="A", ethnicity_code=EthnicCode.HISPANIC)
        ),
        not_hispanic=Count(
            "ncid", filter=Q(registration_status_code="A", ethnicity_code=EthnicCode.NOT_HISPANIC)
        ),
        ethnicity_u=Count(
            "ncid", filter=Q(registration_status_code="A", ethnicity_code=EthnicCode.UNDESIGNATED)
        ),
        # Status (all statuses — no active filter)
        active=Count("ncid", filter=Q(registration_status_code=StatusCode.ACTIVE)),
        denied=Count("ncid", filter=Q(registration_status_code=StatusCode.DENIED)),
        inactive=Count("ncid", filter=Q(registration_status_code=StatusCode.INACTIVE)),
        removed=Count("ncid", filter=Q(registration_status_code=StatusCode.REMOVED)),
        temporary=Count("ncid", filter=Q(registration_status_code=StatusCode.TEMPORARY)),
    )

    sample_voters = qs.values(
        "ncid",
        "gender_sex_code",
        "race_code",
        "registered_party_code",
        "registration_status_code",
    )[:25]

    return render(
        request,
        "ncsbe/county_registrations.html",
        {"county_name": county_name, "stats": stats, "sample_voters": sample_voters},
    )


@cache_page(CACHE_TTL)
def voter_history(request: HttpRequest, ncid: str) -> HttpResponse:
    form = VoterHistoryForm({"ncid": ncid})
    if not form.is_valid():
        raise Http404("Invalid voter ID.")
    ncid = form.cleaned_data["ncid"]

    events = list(VoterEventView.objects.filter(ncid=ncid).order_by("-election_date"))
    voter = VoterView.objects.filter(ncid=ncid).first()

    return render(
        request,
        "ncsbe/voter_history.html",
        {"ncid": ncid, "events": events, "voter": voter},
    )
