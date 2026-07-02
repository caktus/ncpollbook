import factory

from apps.ncsbe.models import Voter, VoterEvent


class VoterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Voter

    ncid = factory.Sequence(lambda n: f"AA{n:06d}")
    county_id = "32"
    county_desc = "DURHAM"
    status_cd = "A"
    voter_status_desc = "ACTIVE"
    party_cd = "DEM"
    gender_code = "F"
    race_code = "W"
    ethnic_code = "NL"
    birth_year = "1985"
    age_at_year_end = "40"
    registr_dt = "01/15/2010"
    precinct_abbrv = "01"
    precinct_desc = "PRECINCT 01"


class VoterEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VoterEvent

    ncid = factory.Sequence(lambda n: f"AA{n:06d}")
    county_desc = "DURHAM"
    election_lbl = "11/05/2024"
    election_desc = "11/05/2024 GENERAL"
    voting_method = "EARLY VOTING IN-PERSON"
    voted_party_cd = "DEM"
    voted_party_desc = "DEMOCRATIC"
    pct_label = "01"
    pct_description = "PRECINCT 01"
