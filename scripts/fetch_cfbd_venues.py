"""
One-time (rarely re-run) fetch of CFBD's venues list, saved as a static
lookup keyed by venueId -> {city, state, dome, latitude, longitude}.
Venues essentially never change (stadiums don't move), so this doesn't
need to run on any regular schedule -- just re-run manually if a new
venue ever shows up unmatched.

Usage: python fetch_cfbd_venues.py [output_path]
"""
import sys
import os
import json
import requests

CFBD_BASE = "https://api.collegefootballdata.com"


def fetch_venues(output_path=None):
    api_key = os.environ.get("CFBD_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    resp = requests.get(f"{CFBD_BASE}/venues", headers=headers, timeout=20)
    resp.raise_for_status()
    venues = resp.json()

    lookup = {}
    for v in venues:
        vid = v.get("id")
        if vid is None:
            continue
        lookup[str(vid)] = {
            "name": v.get("name"),
            "city": v.get("city"),
            "state": v.get("state"),
            "dome": v.get("dome"),
            "latitude": v.get("latitude"),
            "longitude": v.get("longitude"),
        }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(lookup, f, indent=2)
        print(f"Wrote {len(lookup)} venues to {output_path}", file=sys.stderr)

    return lookup


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "cfbd_venues.json"
    fetch_venues(out_path)
