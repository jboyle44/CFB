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
}
