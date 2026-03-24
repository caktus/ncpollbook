from django.db import models


class StatusCode(models.TextChoices):
    ACTIVE = "A", "Active"
    DENIED = "D", "Denied"
    INACTIVE = "I", "Inactive"
    REMOVED = "R", "Removed"
    TEMPORARY = "S", "Temporary"


class RaceCode(models.TextChoices):
    ASIAN = "A", "Asian"
    BLACK = "B", "Black or African American"
    AMERICAN_INDIAN = "I", "American Indian or Alaska Native"
    TWO_OR_MORE = "M", "Two or More Races"
    OTHER = "O", "Other"
    PACIFIC_ISLANDER = "P", "Native Hawaiian or Pacific Islander"
    UNDESIGNATED = "U", "Undesignated"
    WHITE = "W", "White"


class EthnicCode(models.TextChoices):
    HISPANIC = "HL", "Hispanic or Latino"
    NOT_HISPANIC = "NL", "Not Hispanic or Not Latino"
    UNDESIGNATED = "UN", "Undesignated"


class GenderCode(models.TextChoices):
    FEMALE = "F", "Female"
    MALE = "M", "Male"
    UNDESIGNATED = "U", "Undesignated"


class PartyCode(models.TextChoices):
    DEMOCRATIC = "DEM", "Democratic"
    REPUBLICAN = "REP", "Republican"
    UNAFFILIATED = "UNA", "Unaffiliated"
    LIBERTARIAN = "LIB", "Libertarian"
    GREEN = "GRE", "Green"
    CONSTITUTION = "CST", "Constitution"
    NO_LABELS = "NLB", "No Labels"
    JUSTICE_FOR_ALL = "JFA", "Justice For All"
    WE_THE_PEOPLE = "WTP", "We The People"


class VotingMethod(models.TextChoices):
    EARLY_VOTING_IN_PERSON = "EARLY VOTING IN-PERSON", "Early Voting In-Person"
    ABSENTEE_ONESTOP = "ABSENTEE ONESTOP", "Absentee One-Stop"
    ABSENTEE_BY_MAIL = "ABSENTEE BY MAIL", "Absentee by Mail"
    ABSENTEE = "ABSENTEE", "Absentee"
    ELECTION_DAY_IN_PERSON = "ELECTION DAY IN-PERSON", "Election Day In-Person"
    ABSENTEE_CURBSIDE = "ABSENTEE CURBSIDE", "Absentee Curbside"
    EARLY_VOTING_CURBSIDE = "EARLY VOTING CURBSIDE", "Early Voting Curbside"
    ELECTION_DAY_CURBSIDE = "ELECTION DAY CURBSIDE", "Election Day Curbside"
    PROVISIONAL = "PROVISIONAL", "Provisional"
    ELIGIBLE_DID_NOT_VOTE = "ELIGIBLE DID NOT VOTE", "Eligible Did Not Vote"
    TRANSFER = "TRANSFER", "Transfer"
    LEGACY = "LEGACY", "Legacy"


class ElectionType(models.TextChoices):
    PRIMARY = "PRIMARY", "Primary"
    SECOND_PRIMARY = "SECOND_PRIMARY", "Second Primary"
    GENERAL = "GENERAL", "General"
    RUNOFF = "RUNOFF", "Runoff"
    MUNICIPAL = "MUNICIPAL", "Municipal"
    SPECIAL = "SPECIAL", "Special"
    OTHER = "OTHER", "Other"


# NCSBE S3 data download URLs
NCVOTER_ZIP_URL = "https://s3.amazonaws.com/dl.ncsbe.gov/data/ncvoter_Statewide.zip"
NCVHIS_ZIP_URL = "https://s3.amazonaws.com/dl.ncsbe.gov/data/ncvhis_Statewide.zip"

# Tab-delimited filenames inside the downloaded ZIPs
NCVOTER_TXT_FILENAME = "ncvoter_Statewide.txt"
NCVHIS_TXT_FILENAME = "ncvhis_Statewide.txt"

# County name → county_id mapping (Yancey uses "00")
COUNTY_ID_MAP: dict[str, str] = {
    "ALAMANCE": "1",
    "ALEXANDER": "2",
    "ALLEGHANY": "3",
    "ANSON": "4",
    "ASHE": "5",
    "AVERY": "6",
    "BEAUFORT": "7",
    "BERTIE": "8",
    "BLADEN": "9",
    "BRUNSWICK": "10",
    "BUNCOMBE": "11",
    "BURKE": "12",
    "CABARRUS": "13",
    "CALDWELL": "14",
    "CAMDEN": "15",
    "CARTERET": "16",
    "CASWELL": "17",
    "CATAWBA": "18",
    "CHATHAM": "19",
    "CHEROKEE": "20",
    "CHOWAN": "21",
    "CLAY": "22",
    "CLEVELAND": "23",
    "COLUMBUS": "24",
    "CRAVEN": "25",
    "CUMBERLAND": "26",
    "CURRITUCK": "27",
    "DARE": "28",
    "DAVIDSON": "29",
    "DAVIE": "30",
    "DUPLIN": "31",
    "DURHAM": "32",
    "EDGECOMBE": "33",
    "FORSYTH": "34",
    "FRANKLIN": "35",
    "GASTON": "36",
    "GATES": "37",
    "GRAHAM": "38",
    "GRANVILLE": "39",
    "GREENE": "40",
    "GUILFORD": "41",
    "HALIFAX": "42",
    "HARNETT": "43",
    "HAYWOOD": "44",
    "HENDERSON": "45",
    "HERTFORD": "46",
    "HOKE": "47",
    "HYDE": "48",
    "IREDELL": "49",
    "JACKSON": "50",
    "JOHNSTON": "51",
    "JONES": "52",
    "LEE": "53",
    "LENOIR": "54",
    "LINCOLN": "55",
    "MACON": "56",
    "MADISON": "57",
    "MARTIN": "58",
    "MCDOWELL": "59",
    "MECKLENBURG": "60",
    "MITCHELL": "61",
    "MONTGOMERY": "62",
    "MOORE": "63",
    "NASH": "64",
    "NEWHANOVER": "65",
    "NORTHAMPTON": "66",
    "ONSLOW": "67",
    "ORANGE": "68",
    "PAMLICO": "69",
    "PASQUOTANK": "70",
    "PENDER": "71",
    "PERQUIMANS": "72",
    "PERSON": "73",
    "PITT": "74",
    "POLK": "75",
    "RANDOLPH": "76",
    "RICHMOND": "77",
    "ROBESON": "78",
    "ROCKINGHAM": "79",
    "ROWAN": "80",
    "RUTHERFORD": "81",
    "SAMPSON": "82",
    "SCOTLAND": "83",
    "STANLY": "84",
    "STOKES": "85",
    "SURRY": "86",
    "SWAIN": "87",
    "TRANSYLVANIA": "88",
    "TYRRELL": "89",
    "UNION": "90",
    "VANCE": "91",
    "WAKE": "92",
    "WARREN": "93",
    "WASHINGTON": "94",
    "WATAUGA": "95",
    "WAYNE": "96",
    "WILKES": "97",
    "WILSON": "98",
    "YADKIN": "99",
    "YANCEY": "00",
}
