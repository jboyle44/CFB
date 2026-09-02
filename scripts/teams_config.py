"""
Team registry: maps an internal team key to the URL identifiers each source uses.

Ourlads: https://www.ourlads.com/ncaa-football-depth-charts/depth-chart/{ourlads_slug}/{ourlads_id}
247Sports roster: https://247sports.com/team/{sports247_slug}/Roster/

sports247_slug is optional -- teams without one just skip the composite-score/
transfer-rank step (Ourlads depth chart data still populates normally). Only
Ohio State's 247 slug has been verified so far; others can be added the same
way once needed (visit the team's 247Sports roster page and copy the slug
out of the URL).
"""

TEAMS = {
    "illinois": {
        "display_name": "Illinois",
        "ourlads_slug": "illinois",
        "ourlads_id": "90705",
        "sports247_slug": None,
    },
    "indiana": {
        "display_name": "Indiana",
        "ourlads_slug": "indiana",
        "ourlads_id": "90728",
        "sports247_slug": None,
    },
    "iowa": {
        "display_name": "Iowa",
        "ourlads_slug": "iowa",
        "ourlads_id": "90751",
        "sports247_slug": None,
    },
    "maryland": {
        "display_name": "Maryland",
        "ourlads_slug": "maryland",
        "ourlads_id": "91027",
        "sports247_slug": None,
    },
    "michigan": {
        "display_name": "Michigan",
        "ourlads_slug": "michigan",
        "ourlads_id": "91119",
        "sports247_slug": None,
    },
    "michigan-state": {
        "display_name": "Michigan State",
        "ourlads_slug": "michigan-state",
        "ourlads_id": "91142",
        "sports247_slug": None,
    },
    "minnesota": {
        "display_name": "Minnesota",
        "ourlads_slug": "minnesota",
        "ourlads_id": "91188",
        "sports247_slug": None,
    },
    "nebraska": {
        "display_name": "Nebraska",
        "ourlads_slug": "nebraska",
        "ourlads_id": "91303",
        "sports247_slug": None,
    },
    "northwestern": {
        "display_name": "Northwestern",
        "ourlads_slug": "northwestern",
        "ourlads_id": "91464",
        "sports247_slug": None,
    },
    "ohio-state": {
        "display_name": "Ohio State",
        "ourlads_slug": "ohio-state",
        "ourlads_id": "91533",
        "sports247_slug": "ohio-state-buckeyes-football-79",
    },
    "oregon": {
        "display_name": "Oregon",
        "ourlads_slug": "oregon",
        "ourlads_id": "91625",
        "sports247_slug": None,
    },
    "penn-state": {
        "display_name": "Penn State",
        "ourlads_slug": "penn-state",
        "ourlads_id": "91671",
        "sports247_slug": None,
    },
    "purdue": {
        "display_name": "Purdue",
        "ourlads_slug": "purdue",
        "ourlads_id": "91717",
        "sports247_slug": None,
    },
    "rutgers": {
        "display_name": "Rutgers",
        "ourlads_slug": "rutgers",
        "ourlads_id": "91763",
        "sports247_slug": None,
    },
    "ucla": {
        "display_name": "UCLA",
        "ourlads_slug": "ucla",
        "ourlads_id": "92223",
        "sports247_slug": None,
    },
    "usc": {
        "display_name": "USC",
        "ourlads_slug": "usc",
        "ourlads_id": "92269",
        "sports247_slug": None,
    },
    "washington": {
        "display_name": "Washington",
        "ourlads_slug": "washington",
        "ourlads_id": "92453",
        "sports247_slug": None,
    },
    "wisconsin": {
        "display_name": "Wisconsin",
        "ourlads_slug": "wisconsin",
        "ourlads_id": "92545",
        "sports247_slug": None,
    },
    "alabama": {
        "display_name": "Alabama",
        "ourlads_slug": "alabama",
        "ourlads_id": "89923",
        "sports247_slug": None,
    },
    "arkansas": {
        "display_name": "Arkansas",
        "ourlads_slug": "arkansas",
        "ourlads_id": "89992",
        "sports247_slug": None,
    },
    "auburn": {
        "display_name": "Auburn",
        "ourlads_slug": "auburn",
        "ourlads_id": "90061",
        "sports247_slug": None,
    },
    "florida": {
        "display_name": "Florida",
        "ourlads_slug": "florida",
        "ourlads_id": "90498",
        "sports247_slug": None,
    },
    "georgia": {
        "display_name": "Georgia",
        "ourlads_slug": "georgia",
        "ourlads_id": "90590",
        "sports247_slug": None,
    },
    "kentucky": {
        "display_name": "Kentucky",
        "ourlads_slug": "kentucky",
        "ourlads_id": "90866",
        "sports247_slug": None,
    },
    "lsu": {
        "display_name": "LSU",
        "ourlads_slug": "lsu",
        "ourlads_id": "90981",
        "sports247_slug": None,
    },
    "ole-miss": {
        "display_name": "Ole Miss",
        "ourlads_slug": "ole-miss",
        "ourlads_id": "91602",
        "sports247_slug": None,
    },
    "mississippi-state": {
        "display_name": "Mississippi State",
        "ourlads_slug": "mississippi-state",
        "ourlads_id": "91211",
        "sports247_slug": None,
    },
    "missouri": {
        "display_name": "Missouri",
        "ourlads_slug": "missouri",
        "ourlads_id": "91234",
        "sports247_slug": None,
    },
    "oklahoma": {
        "display_name": "Oklahoma",
        "ourlads_slug": "oklahoma",
        "ourlads_id": "91556",
        "sports247_slug": None,
    },
    "south-carolina": {
        "display_name": "South Carolina",
        "ourlads_slug": "south-carolina",
        "ourlads_id": "91832",
        "sports247_slug": None,
    },
    "tennessee": {
        "display_name": "Tennessee",
        "ourlads_slug": "tennessee",
        "ourlads_id": "91993",
        "sports247_slug": None,
    },
    "texas": {
        "display_name": "Texas",
        "ourlads_slug": "texas",
        "ourlads_id": "92016",
        "sports247_slug": None,
    },
    "texas-am": {
        "display_name": "Texas A&M",
        "ourlads_slug": "texas-am",
        "ourlads_id": "92039",
        "sports247_slug": None,
    },
    "vanderbilt": {
        "display_name": "Vanderbilt",
        "ourlads_slug": "vanderbilt",
        "ourlads_id": "92361",
        "sports247_slug": None,
    },
}
