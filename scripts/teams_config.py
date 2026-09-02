"""
Team registry: maps an internal team key to the URL identifiers each source uses.

Ourlads: https://www.ourlads.com/ncaa-football-depth-charts/depth-chart/{ourlads_slug}/{ourlads_id}
247Sports roster: https://247sports.com/team/{sports247_slug}/Roster/

To add a team, find both slugs/IDs by visiting the team's Ourlads depth chart page
and its 247Sports roster page and copying the identifiers out of the URL.
Only Ohio State is wired up for now; add more teams here as they're needed.
"""

TEAMS = {
    "ohio-state": {
        "display_name": "Ohio State",
        "ourlads_slug": "ohio-state",
        "ourlads_id": "91533",
        "sports247_slug": "ohio-state-buckeyes-football-79",
    },
}
