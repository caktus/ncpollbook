from typing import ClassVar

from django.db import models
from django_pgviews import view as pg

ELECTION_TYPE_CASE = """
    CASE
        WHEN election_desc ILIKE '%SECOND PRIMARY%' THEN 'SECOND_PRIMARY'
        WHEN election_desc ILIKE '%CONGRESSIONAL%'  THEN 'PRIMARY'
        WHEN election_desc ILIKE '%PRIMARY%'        THEN 'PRIMARY'
        WHEN election_desc ILIKE '%GENERAL%'        THEN 'GENERAL'
        WHEN election_desc ILIKE '%RUNOFF%'         THEN 'RUNOFF'
        WHEN election_desc ILIKE '%MUNICIPAL%'      THEN 'MUNICIPAL'
        WHEN election_desc ILIKE '%SPECIAL%'        THEN 'SPECIAL'
        ELSE 'OTHER'
    END
"""


class Voter(models.Model):
    """
    Raw voter registration data loaded directly from ncvoter_Statewide.txt.
    All columns are stored as text to match the source file exactly.
    No indexes beyond primary key — optimised for fast COPY loading.
    Linked to VoterEvent via ncid.
    """

    # Geography
    county_id = models.CharField(
        max_length=10, blank=True, verbose_name="County identification number"
    )
    county_desc = models.CharField(max_length=15, blank=True, verbose_name="County name")

    # Voter identifiers
    voter_reg_num = models.CharField(
        max_length=12, blank=True, verbose_name="Voter registration number"
    )
    ncid = models.CharField(
        max_length=12, blank=True, verbose_name="North Carolina identification number; join key"
    )

    # Name (PII — present in raw table, excluded from materialized views)
    last_name = models.CharField(max_length=25, blank=True, verbose_name="Voter last name")
    first_name = models.CharField(max_length=20, blank=True, verbose_name="Voter first name")
    middle_name = models.CharField(max_length=20, blank=True, verbose_name="Voter middle name")
    name_suffix_lbl = models.CharField(max_length=10, blank=True, verbose_name="Voter suffix name")

    # Registration status
    status_cd = models.CharField(max_length=2, blank=True, verbose_name="Registration status code")
    voter_status_desc = models.CharField(
        max_length=25, blank=True, verbose_name="Registration status description"
    )
    reason_cd = models.CharField(
        max_length=2, blank=True, verbose_name="Registration status reason code"
    )
    voter_status_reason_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Registration status reason description"
    )

    # Residential address (PII)
    res_street_address = models.CharField(
        max_length=65, blank=True, verbose_name="Residential street address"
    )
    res_city_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Residential city name"
    )
    state_cd = models.CharField(
        max_length=2, blank=True, verbose_name="Residential address state code"
    )
    zip_code = models.CharField(
        max_length=9, blank=True, verbose_name="Residential address zip code"
    )

    # Mailing address (PII)
    mail_addr1 = models.CharField(max_length=40, blank=True, verbose_name="Mailing address line 1")
    mail_addr2 = models.CharField(max_length=40, blank=True, verbose_name="Mailing address line 2")
    mail_addr3 = models.CharField(max_length=40, blank=True, verbose_name="Mailing address line 3")
    mail_addr4 = models.CharField(max_length=40, blank=True, verbose_name="Mailing address line 4")
    mail_city = models.CharField(
        max_length=30, blank=True, verbose_name="Mailing address city name"
    )
    mail_state = models.CharField(
        max_length=2, blank=True, verbose_name="Mailing address city code"
    )
    mail_zipcode = models.CharField(
        max_length=9, blank=True, verbose_name="Mailing address zip code"
    )

    # Contact (PII)
    full_phone_number = models.CharField(
        max_length=12, blank=True, verbose_name="Full phone number including area code"
    )

    # Flags
    confidential_ind = models.CharField(
        max_length=1, blank=True, verbose_name="Confidential indicator"
    )

    # Registration metadata
    registr_dt = models.CharField(max_length=10, blank=True, verbose_name="Registration date")

    # Demographics
    race_code = models.CharField(max_length=3, blank=True, verbose_name="Race code")
    ethnic_code = models.CharField(max_length=3, blank=True, verbose_name="Ethnicity code")
    party_cd = models.CharField(max_length=3, blank=True, verbose_name="Registered party code")
    gender_code = models.CharField(max_length=1, blank=True, verbose_name="Gender/sex code")
    birth_year = models.CharField(max_length=4, blank=True, verbose_name="Year of birth")
    age_at_year_end = models.CharField(
        max_length=3, blank=True, verbose_name="Age at end of the year"
    )
    birth_state = models.CharField(max_length=2, blank=True, verbose_name="Birth state")

    # ID verification flags
    drivers_lic = models.CharField(max_length=1, blank=True, verbose_name="Drivers license")
    ssn = models.CharField(
        max_length=1, blank=True, verbose_name="Last four of Social Security Number"
    )
    no_dl_ssn_chkbx = models.CharField(
        max_length=1,
        blank=True,
        verbose_name="Voter checked box indicating they do not have DL or SSN number",
    )
    hava_id_req = models.CharField(
        max_length=1, blank=True, verbose_name="HAVA identification required"
    )

    # Jurisdiction codes
    precinct_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Precinct abbreviation"
    )
    precinct_desc = models.CharField(max_length=60, blank=True, verbose_name="Precinct name")
    municipality_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Municipality jurisdiction abbreviation"
    )
    municipality_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Municipality jurisdiction name"
    )
    ward_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Ward jurisdiction abbreviation"
    )
    ward_desc = models.CharField(max_length=60, blank=True, verbose_name="Ward jurisdiction name")
    cong_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Congressional district abbreviation"
    )
    super_court_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Superior court jurisdiction abbreviation"
    )
    judic_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Judicial district abbreviation"
    )
    nc_senate_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="NC Senate jurisdiction abbreviation"
    )
    nc_house_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="NC House jurisdiction abbreviation"
    )
    county_commiss_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="County commissioner jurisdiction abbreviation"
    )
    county_commiss_desc = models.CharField(
        max_length=60, blank=True, verbose_name="County commissioner jurisdiction name"
    )
    township_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Township jurisdiction abbreviation"
    )
    township_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Township jurisdiction name"
    )
    school_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="School district abbreviation"
    )
    school_dist_desc = models.CharField(
        max_length=60, blank=True, verbose_name="School district name"
    )
    fire_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Fire district abbreviation"
    )
    fire_dist_desc = models.CharField(max_length=60, blank=True, verbose_name="Fire district name")
    water_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Water district abbreviation"
    )
    water_dist_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Water district name"
    )
    sewer_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Sewer district abbreviation"
    )
    sewer_dist_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Sewer district name"
    )
    sanit_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Sanitation district abbreviation"
    )
    sanit_dist_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Sanitation district name"
    )
    rescue_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Rescue district abbreviation"
    )
    rescue_dist_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Rescue district name"
    )
    munic_dist_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Municipal district abbreviation"
    )
    munic_dist_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Municipal district name"
    )
    dist_1_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Prosecutorial district abbreviation"
    )
    dist_1_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Prosecutorial district name"
    )
    vtd_abbrv = models.CharField(
        max_length=6, blank=True, verbose_name="Voter tabulation district abbreviation"
    )
    vtd_desc = models.CharField(
        max_length=60, blank=True, verbose_name="Voter tabulation district name"
    )

    def __str__(self) -> str:
        return f"{self.ncid} ({self.county_desc})"


class VoterEvent(models.Model):
    """
    Raw voter history data loaded directly from ncvhis_Statewide.txt.
    All columns are stored as text to match the source file exactly.
    No indexes beyond primary key — optimised for fast COPY loading.
    Linked to Voter via ncid.
    """

    county_id = models.CharField(
        max_length=10, blank=True, verbose_name="County identification number"
    )
    county_desc = models.CharField(max_length=20, blank=True, verbose_name="County name")
    voter_reg_num = models.CharField(
        max_length=12, blank=True, verbose_name="Voter registration number"
    )
    election_lbl = models.CharField(max_length=10, blank=True, verbose_name="Election date label")
    election_desc = models.CharField(
        max_length=230, blank=True, verbose_name="Election description"
    )
    voting_method = models.CharField(max_length=30, blank=True, verbose_name="Voting method")
    voted_party_cd = models.CharField(max_length=3, blank=True, verbose_name="Voted party code")
    voted_party_desc = models.CharField(max_length=60, blank=True, verbose_name="Voted party name")
    pct_label = models.CharField(
        max_length=6,
        blank=True,
        help_text="Precinct code for voter at time of election (see election_lbl)",
    )
    pct_description = models.CharField(
        max_length=60,
        blank=True,
        help_text="Precinct name for voter at time of election (see election_lbl)",
    )
    ncid = models.CharField(
        max_length=12, blank=True, verbose_name="North Carolina identification number; join key"
    )
    voted_county_id = models.CharField(
        max_length=3,
        blank=True,
        help_text="The county id number in which the voter voted in the election (see election_lbl)",
    )
    voted_county_desc = models.CharField(
        max_length=60,
        blank=True,
        help_text="The county name in which the voter voted in the election (see election_lbl)",
    )
    vtd_label = models.CharField(
        max_length=6,
        blank=True,
        help_text="Voter tabulation district label for voter at time of election (see election_lbl)",
    )
    vtd_description = models.CharField(
        max_length=60,
        blank=True,
        help_text="Voter tabulation district name for voter at time of election (see election_lbl)",
    )

    def __str__(self) -> str:
        return f"{self.ncid} — {self.election_lbl}"


# ---------------------------------------------------------------------------
# Materialized Views
# ---------------------------------------------------------------------------


class VoterView(pg.MaterializedView):
    """
    One row per registered voter. Excludes all PII columns.
    Covers all statuses. Casts char fields to appropriate types for clean querying.

    Indexes:
      - UNIQUE on ncid (used for joins with VoterEventView)
      - Composite: county_name, registered_party_code, registration_status_code
      - age_at_end_of_year, gender_sex_code, race_code, registration_date
    """

    concurrent_index = "ncid"

    sql = """
        SELECT
            -- Geography
            county_id::smallint                         AS county_identification_number,
            county_desc                                 AS county_name,
            municipality_desc                           AS municipality_jurisdiction_name,

            -- Voter identity (no PII)
            ncid,
            status_cd                                   AS registration_status_code,
            party_cd                                    AS registered_party_code,
            gender_code                                 AS gender_sex_code,
            race_code,
            ethnic_code                                 AS ethnicity_code,

            -- Age (cast from char to int; invalid values become NULL)
            NULLIF(TRIM(birth_year), '')::smallint      AS year_of_birth,
            NULLIF(TRIM(age_at_year_end), '')::smallint AS age_at_end_of_year,

            -- Registration metadata
            CASE WHEN TRIM(registr_dt) ~ '^\\d{2}/\\d{2}/\\d{4}$'
                 THEN TRIM(registr_dt)::date END AS registration_date,
            date_part('year', CASE WHEN TRIM(registr_dt) ~ '^\\d{2}/\\d{2}/\\d{4}$'
                 THEN TRIM(registr_dt)::date END)::smallint AS registration_year

        FROM ncsbe_voter
        WHERE TRIM(birth_year) ~ '^[0-9]{4}$'
    """

    county_identification_number = models.SmallIntegerField(null=True)
    county_name = models.CharField(
        max_length=15,
        blank=True,
        db_comment="County name: ALAMANCE, ALEXANDER, ALLEGHANY, ANSON, ASHE, AVERY, BEAUFORT, BERTIE, BLADEN, BRUNSWICK, BUNCOMBE, BURKE, CABARRUS, CALDWELL, CAMDEN, CARTERET, CASWELL, CATAWBA, CHATHAM, CHEROKEE ... (100 distinct)",
    )
    municipality_jurisdiction_name = models.CharField(max_length=60, blank=True)
    ncid = models.CharField(
        max_length=12,
        primary_key=True,
        verbose_name="North Carolina identification number; join key",
        db_comment="Unique voter ID; join to VoterEventView on ncid",
    )
    registration_status_code = models.CharField(
        max_length=2,
        blank=True,
        db_comment="A=ACTIVE, D=DENIED, I=INACTIVE, R=REMOVED (4 distinct)",
    )
    registered_party_code = models.CharField(
        max_length=3,
        blank=True,
        db_comment="Party affiliation: DEM, GRE, LIB, REP, UNA (5 distinct)",
    )
    gender_sex_code = models.CharField(
        max_length=1, blank=True, db_comment="M=Male F=Female U=Undesignated"
    )
    race_code = models.CharField(
        max_length=3,
        blank=True,
        db_comment="W=White, B=Black, A=Asian, M=Multiracial, O=Other, I=Am.Indian, U=Undesignated",
    )
    ethnicity_code = models.CharField(
        max_length=3,
        blank=True,
        db_comment="HL=Hispanic/Latino, NL=Not Hispanic/Latino, UN=Undesignated",
    )
    year_of_birth = models.SmallIntegerField(null=True)
    age_at_end_of_year = models.SmallIntegerField(null=True)
    registration_date = models.DateField(null=True)
    registration_year = models.SmallIntegerField(null=True)

    class Meta:
        managed = False
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["county_name"], name="voter_view_county_name_idx"),
        ]

    def __str__(self) -> str:
        return str(self.ncid)


class VoterEventView(pg.MaterializedView):
    """
    One row per vote cast per voter per election.
    election_lbl is cast to a proper date.
    election_type is derived from election_desc using ordered CASE matching
    (SECOND_PRIMARY must precede PRIMARY to avoid misclassification).

    Note on voting_method:
      - 'ELIGIBLE DID NOT VOTE' and 'TRANSFER' are administrative records
        and should be excluded when computing turnout.

    """

    concurrent_index = "id"

    sql = f"""
        SELECT
            ROW_NUMBER() OVER ()                 AS id,
            ncid,
            voted_county_desc,

            -- Election identity
            election_lbl::date                   AS election_date,
            {ELECTION_TYPE_CASE}                 AS election_type,
            date_part('year', election_lbl::date)::smallint AS election_year,

            -- Voting behaviour
            voting_method,
            voted_party_desc                     AS voted_party_name

        FROM ncsbe_voterevent
    """

    id = models.BigIntegerField(primary_key=True)
    ncid = models.CharField(
        max_length=12,
        verbose_name="North Carolina identification number; join key",
        db_comment="Voter ID; join to VoterView on ncid",
    )
    voted_county_desc = models.CharField(
        max_length=60,
        blank=True,
        help_text="The county name in which the voter voted in the election (see election_lbl)",
    )
    election_date = models.DateField(null=True)
    election_type = models.CharField(
        max_length=20,
        blank=True,
        db_comment="GENERAL, MUNICIPAL, OTHER, PRIMARY, RUNOFF, SECOND_PRIMARY (6 distinct)",
    )
    election_year = models.SmallIntegerField(null=True)
    voting_method = models.CharField(
        max_length=30,
        blank=True,
        db_comment="ABSENTEE, ABSENTEE BY MAIL, ABSENTEE CURBSIDE, ABSENTEE ONESTOP, EARLY VOTING CURBSIDE, EARLY VOTING IN-PERSON, ELECTION DAY CURBSIDE, ELECTION DAY IN-PERSON, ELIGIBLE DID NOT VOTE, LEGACY, PROVISIONAL, TRANSFER (12 distinct)",
    )
    voted_party_name = models.CharField(
        max_length=60,
        blank=True,
        db_comment="(empty), CONSTITUTION, DEMOCRATIC, GREEN, JUSTICE FOR ALL, LIBERTARIAN, NO LABELS, REPUBLICAN, UNAFFILIATED, WE THE PEOPLE (10 distinct)",
    )

    class Meta:
        managed = False
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["ncid"], name="voter_event_view_ncid_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.ncid} — {self.election_date}"
