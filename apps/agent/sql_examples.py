"""Few-shot SQL examples for the sql_gen_agent system prompt."""

SQL_EXAMPLE_1 = """\
-- 1. Gender Gap by Geography
-- Top 5 counties by absolute disparity between registered male and female voters.
WITH county_gender_counts AS (
    SELECT
        county_name,
        COUNT(*) FILTER (WHERE gender_sex_code = 'M') AS male_count,
        COUNT(*) FILTER (WHERE gender_sex_code = 'F') AS female_count,
        COUNT(*) AS total_voters
    FROM ncsbe_voterview
    WHERE gender_sex_code IN ('M', 'F')
    GROUP BY 1
),
gender_disparity_calc AS (
    SELECT
        county_name,
        male_count,
        female_count,
        ABS(male_count - female_count) AS absolute_gap,
        ROUND((ABS(male_count - female_count)::numeric / total_voters) * 100, 2) AS percentage_gap
    FROM county_gender_counts
)
SELECT
    county_name,
    male_count,
    female_count,
    absolute_gap,
    percentage_gap
FROM gender_disparity_calc
ORDER BY absolute_gap DESC
LIMIT 5;"""

SQL_EXAMPLE_2 = """\
-- 2. Preferred Voting Methods by Party
-- Compares One-Stop early voting vs Mail-in absentee across UNA, DEM, REP.
WITH method_totals AS (
    SELECT
        v.registered_party_code,
        COUNT(*) FILTER (WHERE e.voting_method = 'ABSENTEE ONESTOP') AS onestop_votes,
        COUNT(*) FILTER (WHERE e.voting_method = 'ABSENTEE BY MAIL') AS mail_in_votes,
        COUNT(*) AS total_votes_cast
    FROM ncsbe_voterview v
    JOIN ncsbe_votereventview e ON v.ncid = e.ncid
    WHERE v.registered_party_code IN ('UNA', 'DEM', 'REP')
    GROUP BY 1
)
SELECT
    registered_party_code,
    ROUND((onestop_votes::numeric / total_votes_cast) * 100, 2) AS pct_onestop,
    ROUND((mail_in_votes::numeric / total_votes_cast) * 100, 2) AS pct_mail_in,
    CASE
        WHEN onestop_votes > mail_in_votes THEN 'Prefers One-Stop'
        ELSE 'Prefers Mail-in'
    END AS primary_preference
FROM method_totals;"""

SQL_EXAMPLE_3 = """\
-- 3. The 'Primary' Drop-off
-- Percentage of 2020 General voters who did not return for the 2022 Primary.
WITH general_2020_voters AS (
    SELECT DISTINCT ncid
    FROM ncsbe_votereventview
    WHERE election_date = '2020-11-03'
      AND election_type = 'GENERAL'
),
primary_2022_voters AS (
    SELECT DISTINCT ncid
    FROM ncsbe_votereventview
    WHERE election_year = 2022
      AND election_type = 'PRIMARY'
),
retention_stats AS (
    SELECT
        COUNT(g.ncid) AS total_2020_gen_voters,
        COUNT(p.ncid) AS returned_in_2022_primary
    FROM general_2020_voters g
    LEFT JOIN primary_2022_voters p ON g.ncid = p.ncid
)
SELECT
    total_2020_gen_voters,
    returned_in_2022_primary,
    ROUND((returned_in_2022_primary::numeric / total_2020_gen_voters) * 100, 2) AS retention_rate,
    (100 - ROUND((returned_in_2022_primary::numeric / total_2020_gen_voters) * 100, 2)) AS drop_off_rate
FROM retention_stats;"""

SQL_EXAMPLE_4 = """\
-- 4. Consistent "Super-Voters"
-- Voters who participated in every General or Primary election in the last 4 years.
WITH eligible_elections AS (
    SELECT COUNT(DISTINCT election_date) AS total_major_elections
    FROM ncsbe_votereventview
    WHERE election_year >= 2022
      AND election_type IN ('GENERAL', 'PRIMARY')
),
voter_participation AS (
    SELECT
        ncid,
        COUNT(DISTINCT election_date) AS elections_attended
    FROM ncsbe_votereventview
    WHERE election_year >= 2022
      AND election_type IN ('GENERAL', 'PRIMARY')
    GROUP BY 1
)
SELECT
    COUNT(vp.ncid) AS super_voter_count,
    (SELECT total_major_elections FROM eligible_elections) AS elections_required
FROM voter_participation vp
CROSS JOIN eligible_elections ee
WHERE vp.elections_attended = ee.total_major_elections;"""

SQL_EXAMPLE_5 = """\
-- 5. The "Unaffiliated" Rise
-- Unaffiliated registration share among new voters vs legacy voters.
WITH registration_cohorts AS (
    SELECT
        ncid,
        registered_party_code,
        CASE
            WHEN registration_date >= CURRENT_DATE - INTERVAL '2 years' THEN 'New (Last 2 Years)'
            WHEN registration_date <= CURRENT_DATE - INTERVAL '10 years' THEN 'Legacy (10+ Years)'
            ELSE 'Intermediate'
        END AS cohort
    FROM ncsbe_voterview
    WHERE registration_status_code = 'A'
)
SELECT
    cohort,
    COUNT(*) AS total_in_cohort,
    COUNT(*) FILTER (WHERE registered_party_code = 'UNA') AS una_count,
    ROUND(
        (COUNT(*) FILTER (WHERE registered_party_code = 'UNA')::numeric / COUNT(*)) * 100,
        2
    ) AS una_percentage
FROM registration_cohorts
WHERE cohort IN ('New (Last 2 Years)', 'Legacy (10+ Years)')
GROUP BY 1
ORDER BY 1 DESC;"""

SQL_EXAMPLES: list[str] = [
    SQL_EXAMPLE_1,
    SQL_EXAMPLE_2,
    SQL_EXAMPLE_3,
    SQL_EXAMPLE_4,
    SQL_EXAMPLE_5,
]
