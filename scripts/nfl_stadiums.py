"""
Static NFL stadium lookup, keyed by home team display name (matching
lines_data_nfl.json's homeTeam field). No API needed -- there are only 32
teams and stadiums rarely change, so this is hand-maintained rather than
fetched. Verified against current 2026-season stadium names/sponsors as of
this file's creation; a few notes on tricky cases:
  - Buffalo Bills: brand-new stadium for the 2026 season (also named
    "Highmark Stadium", a different building than their old one).
  - Washington Commanders: FedEx's naming deal ended; current sponsor is
    Northwest (Northwest Stadium), not FedExField.
  - Tennessee Titans: their new stadium doesn't open until Feb 2027, so
    Nissan Stadium is still correct for the 2026 season.
  - Los Angeles Rams and Chargers share SoFi Stadium.
  - "dome" is True for anything with a fixed or retractable roof that's
    normally closed/controlled -- i.e. not subject to outdoor weather during
    a game -- rather than strictly "never open to the sky".
"""

NFL_STADIUMS = {
    "Arizona Cardinals": {"venue": "State Farm Stadium", "city": "Glendale", "state": "AZ", "dome": True, "lat": 33.5276, "lon": -112.2626},
    "Atlanta Falcons": {"venue": "Mercedes-Benz Stadium", "city": "Atlanta", "state": "GA", "dome": True, "lat": 33.7554, "lon": -84.4008},
    "Baltimore Ravens": {"venue": "M&T Bank Stadium", "city": "Baltimore", "state": "MD", "dome": False, "lat": 39.278, "lon": -76.6227},
    "Buffalo Bills": {"venue": "Highmark Stadium", "city": "Orchard Park", "state": "NY", "dome": False, "lat": 42.7738, "lon": -78.787},
    "Carolina Panthers": {"venue": "Bank of America Stadium", "city": "Charlotte", "state": "NC", "dome": False, "lat": 35.2258, "lon": -80.8528},
    "Chicago Bears": {"venue": "Soldier Field", "city": "Chicago", "state": "IL", "dome": False, "lat": 41.8623, "lon": -87.6167},
    "Cincinnati Bengals": {"venue": "Paycor Stadium", "city": "Cincinnati", "state": "OH", "dome": False, "lat": 39.0954, "lon": -84.516},
    "Cleveland Browns": {"venue": "Huntington Bank Field", "city": "Cleveland", "state": "OH", "dome": False, "lat": 41.5061, "lon": -81.6995},
    "Dallas Cowboys": {"venue": "AT&T Stadium", "city": "Arlington", "state": "TX", "dome": True, "lat": 32.7473, "lon": -97.0945},
    "Denver Broncos": {"venue": "Empower Field at Mile High", "city": "Denver", "state": "CO", "dome": False, "lat": 39.7439, "lon": -105.0201},
    "Detroit Lions": {"venue": "Ford Field", "city": "Detroit", "state": "MI", "dome": True, "lat": 42.34, "lon": -83.0456},
    "Green Bay Packers": {"venue": "Lambeau Field", "city": "Green Bay", "state": "WI", "dome": False, "lat": 44.5013, "lon": -88.0622},
    "Houston Texans": {"venue": "NRG Stadium", "city": "Houston", "state": "TX", "dome": True, "lat": 29.6847, "lon": -95.4107},
    "Indianapolis Colts": {"venue": "Lucas Oil Stadium", "city": "Indianapolis", "state": "IN", "dome": True, "lat": 39.7601, "lon": -86.1639},
    "Jacksonville Jaguars": {"venue": "EverBank Stadium", "city": "Jacksonville", "state": "FL", "dome": False, "lat": 30.3239, "lon": -81.6373},
    "Kansas City Chiefs": {"venue": "GEHA Field at Arrowhead Stadium", "city": "Kansas City", "state": "MO", "dome": False, "lat": 39.0489, "lon": -94.4839},
    "Las Vegas Raiders": {"venue": "Allegiant Stadium", "city": "Las Vegas", "state": "NV", "dome": True, "lat": 36.0909, "lon": -115.1833},
    "Los Angeles Chargers": {"venue": "SoFi Stadium", "city": "Inglewood", "state": "CA", "dome": True, "lat": 33.9535, "lon": -118.3392},
    "Los Angeles Rams": {"venue": "SoFi Stadium", "city": "Inglewood", "state": "CA", "dome": True, "lat": 33.9535, "lon": -118.3392},
    "Miami Dolphins": {"venue": "Hard Rock Stadium", "city": "Miami Gardens", "state": "FL", "dome": False, "lat": 25.958, "lon": -80.2389},
    "Minnesota Vikings": {"venue": "U.S. Bank Stadium", "city": "Minneapolis", "state": "MN", "dome": True, "lat": 44.9738, "lon": -93.2575},
    "New England Patriots": {"venue": "Gillette Stadium", "city": "Foxborough", "state": "MA", "dome": False, "lat": 42.0909, "lon": -71.2643},
    "New Orleans Saints": {"venue": "Caesars Superdome", "city": "New Orleans", "state": "LA", "dome": True, "lat": 29.9511, "lon": -90.0812},
    "New York Giants": {"venue": "MetLife Stadium", "city": "East Rutherford", "state": "NJ", "dome": False, "lat": 40.8135, "lon": -74.0745},
    "New York Jets": {"venue": "MetLife Stadium", "city": "East Rutherford", "state": "NJ", "dome": False, "lat": 40.8135, "lon": -74.0745},
    "Philadelphia Eagles": {"venue": "Lincoln Financial Field", "city": "Philadelphia", "state": "PA", "dome": False, "lat": 39.9008, "lon": -75.1675},
    "Pittsburgh Steelers": {"venue": "Acrisure Stadium", "city": "Pittsburgh", "state": "PA", "dome": False, "lat": 40.4468, "lon": -80.0158},
    "San Francisco 49ers": {"venue": "Levi's Stadium", "city": "Santa Clara", "state": "CA", "dome": False, "lat": 37.4033, "lon": -121.9694},
    "Seattle Seahawks": {"venue": "Lumen Field", "city": "Seattle", "state": "WA", "dome": False, "lat": 47.5952, "lon": -122.3316},
    "Tampa Bay Buccaneers": {"venue": "Raymond James Stadium", "city": "Tampa", "state": "FL", "dome": False, "lat": 27.9759, "lon": -82.5033},
    "Tennessee Titans": {"venue": "Nissan Stadium", "city": "Nashville", "state": "TN", "dome": False, "lat": 36.1665, "lon": -86.7713},
    "Washington Commanders": {"venue": "Northwest Stadium", "city": "Landover", "state": "MD", "dome": False, "lat": 38.9077, "lon": -76.8645},
}
