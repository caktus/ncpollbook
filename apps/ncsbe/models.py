from django.db import models

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
    county_id = models.CharField(max_length=10, blank=True)
    county_desc = models.CharField(max_length=15, blank=True)

    # Voter identifiers
    voter_reg_num = models.CharField(max_length=12, blank=True)
    ncid = models.CharField(max_length=12, blank=True)

    # Name (PII — present in raw table, excluded from materialized views)
    last_name = models.CharField(max_length=25, blank=True)
    first_name = models.CharField(max_length=20, blank=True)
    middle_name = models.CharField(max_length=20, blank=True)
    name_suffix_lbl = models.CharField(max_length=10, blank=True)

    # Registration status
    status_cd = models.CharField(max_length=2, blank=True)
    voter_status_desc = models.CharField(max_length=25, blank=True)
    reason_cd = models.CharField(max_length=2, blank=True)
    voter_status_reason_desc = models.CharField(max_length=60, blank=True)

    # Residential address (PII)
    res_street_address = models.CharField(max_length=65, blank=True)
    res_city_desc = models.CharField(max_length=60, blank=True)
    state_cd = models.CharField(max_length=2, blank=True)
    zip_code = models.CharField(max_length=9, blank=True)

    # Mailing address (PII)
    mail_addr1 = models.CharField(max_length=40, blank=True)
    mail_addr2 = models.CharField(max_length=40, blank=True)
    mail_addr3 = models.CharField(max_length=40, blank=True)
    mail_addr4 = models.CharField(max_length=40, blank=True)
    mail_city = models.CharField(max_length=30, blank=True)
    mail_state = models.CharField(max_length=2, blank=True)
    mail_zipcode = models.CharField(max_length=9, blank=True)

    # Contact (PII)
    full_phone_number = models.CharField(max_length=12, blank=True)

    # Flags
    confidential_ind = models.CharField(max_length=1, blank=True)

    # Registration metadata
    registr_dt = models.CharField(max_length=10, blank=True)

    # Demographics
    race_code = models.CharField(max_length=3, blank=True)
    ethnic_code = models.CharField(max_length=3, blank=True)
    party_cd = models.CharField(max_length=3, blank=True)
    gender_code = models.CharField(max_length=1, blank=True)
    birth_year = models.CharField(max_length=4, blank=True)
    age_at_year_end = models.CharField(max_length=3, blank=True)
    birth_state = models.CharField(max_length=2, blank=True)

    # ID verification flags
    drivers_lic = models.CharField(max_length=1, blank=True)
    ssn = models.CharField(max_length=1, blank=True)
    no_dl_ssn_chkbx = models.CharField(max_length=1, blank=True)
    hava_id_req = models.CharField(max_length=1, blank=True)

    # Jurisdiction codes
    precinct_abbrv = models.CharField(max_length=6, blank=True)
    precinct_desc = models.CharField(max_length=60, blank=True)
    municipality_abbrv = models.CharField(max_length=6, blank=True)
    municipality_desc = models.CharField(max_length=60, blank=True)
    ward_abbrv = models.CharField(max_length=6, blank=True)
    ward_desc = models.CharField(max_length=60, blank=True)
    cong_dist_abbrv = models.CharField(max_length=6, blank=True)
    super_court_abbrv = models.CharField(max_length=6, blank=True)
    judic_dist_abbrv = models.CharField(max_length=6, blank=True)
    nc_senate_abbrv = models.CharField(max_length=6, blank=True)
    nc_house_abbrv = models.CharField(max_length=6, blank=True)
    county_commiss_abbrv = models.CharField(max_length=6, blank=True)
    county_commiss_desc = models.CharField(max_length=60, blank=True)
    township_abbrv = models.CharField(max_length=6, blank=True)
    township_desc = models.CharField(max_length=60, blank=True)
    school_dist_abbrv = models.CharField(max_length=6, blank=True)
    school_dist_desc = models.CharField(max_length=60, blank=True)
    fire_dist_abbrv = models.CharField(max_length=6, blank=True)
    fire_dist_desc = models.CharField(max_length=60, blank=True)
    water_dist_abbrv = models.CharField(max_length=6, blank=True)
    water_dist_desc = models.CharField(max_length=60, blank=True)
    sewer_dist_abbrv = models.CharField(max_length=6, blank=True)
    sewer_dist_desc = models.CharField(max_length=60, blank=True)
    sanit_dist_abbrv = models.CharField(max_length=6, blank=True)
    sanit_dist_desc = models.CharField(max_length=60, blank=True)
    rescue_dist_abbrv = models.CharField(max_length=6, blank=True)
    rescue_dist_desc = models.CharField(max_length=60, blank=True)
    munic_dist_abbrv = models.CharField(max_length=6, blank=True)
    munic_dist_desc = models.CharField(max_length=60, blank=True)
    dist_1_abbrv = models.CharField(max_length=6, blank=True)
    dist_1_desc = models.CharField(max_length=60, blank=True)
    vtd_abbrv = models.CharField(max_length=6, blank=True)
    vtd_desc = models.CharField(max_length=60, blank=True)

    def __str__(self) -> str:
        return f"{self.ncid} ({self.county_desc})"


class VoterEvent(models.Model):
    """
    Raw voter history data loaded directly from ncvhis_Statewide.txt.
    All columns are stored as text to match the source file exactly.
    No indexes beyond primary key — optimised for fast COPY loading.
    Linked to Voter via ncid.
    """

    county_id = models.CharField(max_length=10, blank=True)
    county_desc = models.CharField(max_length=20, blank=True)
    voter_reg_num = models.CharField(max_length=12, blank=True)
    election_lbl = models.CharField(max_length=10, blank=True)
    election_desc = models.CharField(max_length=230, blank=True)
    voting_method = models.CharField(max_length=30, blank=True)
    voted_party_cd = models.CharField(max_length=3, blank=True)
    voted_party_desc = models.CharField(max_length=60, blank=True)
    pct_label = models.CharField(max_length=6, blank=True)
    pct_description = models.CharField(max_length=60, blank=True)
    ncid = models.CharField(max_length=12, blank=True)
    voted_county_id = models.CharField(max_length=3, blank=True)
    voted_county_desc = models.CharField(max_length=60, blank=True)
    vtd_label = models.CharField(max_length=6, blank=True)
    vtd_description = models.CharField(max_length=60, blank=True)

    def __str__(self) -> str:
        return f"{self.ncid} — {self.election_lbl}"


# # ---------------------------------------------------------------------------
# # Materialized Views
# # ---------------------------------------------------------------------------


# class MvVoterRegistration(pgviews.MaterializedView):
#     """
#     One row per registered voter. Excludes all PII columns.
#     Covers active (A) and inactive (I) voters only.
#     Casts char fields to appropriate types for clean querying.

#     Indexes:
#       - UNIQUE on ncid (used for joins with mv_voter_history)
#       - Composite: county_desc, party_cd, status_cd
#       - age_at_year_end, gender_code, race_code, registr_dt
#     """

#     concurrent_index = "ncid"

#     sql = """
#         SELECT
#             -- Geography
#             county_id::smallint,
#             county_desc,
#             precinct_abbrv,
#             precinct_desc,
#             cong_dist_abbrv,
#             nc_senate_abbrv,
#             nc_house_abbrv,
#             municipality_desc,

#             -- Voter identity (no PII)
#             ncid,
#             status_cd,
#             voter_status_desc,
#             party_cd,
#             gender_code,
#             race_code,
#             ethnic_code,

#             -- Age (cast from char to int; invalid values become NULL)
#             NULLIF(TRIM(birth_year), '')::smallint    AS birth_year,
#             NULLIF(TRIM(age_at_year_end), '')::smallint AS age_at_year_end,

#             -- Registration metadata
#             NULLIF(TRIM(registr_dt), 'xx/xx/xxxx')::date AS registr_dt,
#             date_part('year', NULLIF(TRIM(registr_dt), 'xx/xx/xxxx')::date)::smallint AS registr_year

#         FROM ncvoter_statewide
#         WHERE status_cd IN ('A', 'I')
#           AND TRIM(birth_year) ~ '^[0-9]{{4}}$'
#     """

#     county_id = models.SmallIntegerField(null=True)
#     county_desc = models.CharField(max_length=15, blank=True)
#     precinct_abbrv = models.CharField(max_length=6, blank=True)
#     precinct_desc = models.CharField(max_length=60, blank=True)
#     cong_dist_abbrv = models.CharField(max_length=6, blank=True)
#     nc_senate_abbrv = models.CharField(max_length=6, blank=True)
#     nc_house_abbrv = models.CharField(max_length=6, blank=True)
#     municipality_desc = models.CharField(max_length=60, blank=True)
#     ncid = models.CharField(max_length=12, primary_key=True)
#     status_cd = models.CharField(max_length=2, blank=True)
#     voter_status_desc = models.CharField(max_length=25, blank=True)
#     party_cd = models.CharField(max_length=3, blank=True)
#     gender_code = models.CharField(max_length=1, blank=True)
#     race_code = models.CharField(max_length=3, blank=True)
#     ethnic_code = models.CharField(max_length=3, blank=True)
#     birth_year = models.SmallIntegerField(null=True)
#     age_at_year_end = models.SmallIntegerField(null=True)
#     registr_dt = models.DateField(null=True)
#     registr_year = models.SmallIntegerField(null=True)

#     class Meta:
#         app_label = "ncsbe"
#         db_table = "mv_voter_registration"
#         managed = False

#     def __str__(self) -> str:
#         return str(self.ncid)


# class MvVoterHistory(pgviews.MaterializedView):
#     """
#     One row per vote cast per voter per election.
#     election_lbl is cast to a proper date.
#     election_type is derived from election_desc using ordered CASE matching
#     (SECOND_PRIMARY must precede PRIMARY to avoid misclassification).

#     Note on voting_method:
#       - 'ELIGIBLE DID NOT VOTE' and 'TRANSFER' are administrative records
#         and should be excluded when computing turnout.

#     Note on voted_party_cd:
#       - Empty string values exist; queries grouping by this column should
#         handle them explicitly (filter or label as 'Unknown').
#     """

#     concurrent_index = "id"

#     sql = f"""
#         SELECT
#             ROW_NUMBER() OVER ()                 AS id,
#             ncid,
#             county_desc,
#             voted_county_desc,

#             -- Election identity
#             election_lbl::date                   AS election_date,
#             election_desc,
#             {ELECTION_TYPE_CASE}                 AS election_type,
#             date_part('year', election_lbl::date)::smallint AS election_year,

#             -- Voting behaviour
#             voting_method,
#             voted_party_cd,
#             voted_party_desc

#         FROM ncvhis_statewide
#     """

#     id = models.BigIntegerField(primary_key=True)
#     ncid = models.CharField(max_length=12)
#     county_desc = models.CharField(max_length=20, blank=True)
#     voted_county_desc = models.CharField(max_length=60, blank=True)
#     election_date = models.DateField(null=True)
#     election_desc = models.CharField(max_length=230, blank=True)
#     election_type = models.CharField(max_length=20, blank=True)
#     election_year = models.SmallIntegerField(null=True)
#     voting_method = models.CharField(max_length=30, blank=True)
#     voted_party_cd = models.CharField(max_length=3, blank=True)
#     voted_party_desc = models.CharField(max_length=60, blank=True)

#     class Meta:
#         app_label = "ncsbe"
#         db_table = "mv_voter_history"
#         managed = False

#     def __str__(self) -> str:
#         return f"{self.ncid} — {self.election_date}"


# class MvElections(pgviews.MaterializedView):
#     """
#     Small lookup table of distinct elections with vote counts (~117 rows).
#     Include verbatim in the agent system prompt so the model knows exactly
#     which elections exist before writing any query.

#     Multiple rows can share the same election_date (e.g. 10/08/2019 has 16
#     distinct descriptions). Always filter by election_type or election_desc
#     in addition to election_date to avoid double-counting.
#     """

#     concurrent_index = "id"

#     sql = f"""
#         SELECT
#             ROW_NUMBER() OVER (ORDER BY election_lbl::date DESC, election_desc) AS id,
#             election_lbl::date                   AS election_date,
#             election_desc,
#             {ELECTION_TYPE_CASE}                 AS election_type,
#             date_part('year', election_lbl::date)::smallint AS election_year,
#             COUNT(*)                             AS total_votes
#         FROM ncvhis_statewide
#         GROUP BY election_lbl, election_desc
#         ORDER BY election_date DESC
#     """

#     id = models.BigIntegerField(primary_key=True)
#     election_date = models.DateField(null=True)
#     election_desc = models.CharField(max_length=230, blank=True)
#     election_type = models.CharField(max_length=20, blank=True)
#     election_year = models.SmallIntegerField(null=True)
#     total_votes = models.BigIntegerField(null=True)

#     class Meta:
#         app_label = "ncsbe"
#         db_table = "mv_elections"
#         managed = False

#     def __str__(self) -> str:
#         return f"{self.election_date} — {self.election_desc}"
