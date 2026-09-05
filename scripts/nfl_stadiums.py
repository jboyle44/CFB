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
    "Arizona Cardinals": {"venue": "State Farm Stadium", "city": "Glendale", "state": "AZ", "dome": True},
    "Atlanta Falcons": {"venue": "Mercedes-Benz Stadium", "city": "Atlanta", "state": "GA", "dome": True},
    "Baltimore Ravens": {"venue": "M&T Bank Stadium", "city": "Baltimore", "state": "MD", "dome": False},
    "Buffalo Bills": {"venue": "Highmark Stadium", "city": "Orchard Park", "state": "NY", "dome": False},
    "Carolina Panthers": {"venue": "Bank of America Stadium", "city": "Charlotte", "state": "NC", "dome": False},
    "Chicago Bears": {"venue": "Soldier Field", "city": "Chicago", "state": "IL", "dome": False},
    "Cincinnati Bengals": {"venue": "Paycor Stadium", "city": "Cincinnati", "state": "OH", "dome": False},
    "Cleveland Browns": {"venue": "Huntington Bank Field", "city": "Cleveland", "state": "OH", "dome": False},
    "Dallas Cowboys": {"venue": "AT&T Stadium", "city": "Arlington", "state": "TX", "dome": True},
    "Denver Broncos": {"venue": "Empower Field at Mile High", "city": "Denver", "state": "CO", "dome": False},
    "Detroit Lions": {"venue": "Ford Field", "city": "Detroit", "state": "MI", "dome": True},
    "Green Bay Packers": {"venue": "Lambeau Field", "city": "Green Bay", "state": "WI", "dome": False},
    "Houston Texans": {"venue": "NRG Stadium", "city": "Houston", "state": "TX", "dome": True},
    "Indianapolis Colts": {"venue": "Lucas Oil Stadium", "city": "Indianapolis", "state": "IN", "dome": True},
    "Jacksonville Jaguars": {"venue": "EverBank Stadium", "city": "Jacksonville", "state": "FL", "dome": False},
    "Kansas City Chiefs": {"venue": "GEHA Field at Arrowhead Stadium", "city": "Kansas City", "state": "MO", "dome": False},
    "Las Vegas Raiders": {"venue": "Allegiant Stadium", "city": "Las Vegas", "state": "NV", "dome": True},
    "Los Angeles Chargers": {"venue": "SoFi Stadium", "city": "Inglewood", "state": "CA", "dome": True},
    "Los Angeles Rams": {"venue": "SoFi Stadium", "city": "Inglewood", "state": "CA", "dome": True},
    "Miami Dolphins": {"venue": "Hard Rock Stadium", "city": "Miami Gardens", "state": "FL", "dome": False},
    "Minnesota Vikings": {"venue": "U.S. Bank Stadium", "city": "Minneapolis", "state": "MN", "dome": True},
    "New England Patriots": {"venue": "Gillette Stadium", "city": "Foxborough", "state": "MA", "dome": False},
    "New Orleans Saints": {"venue": "Caesars Superdome", "city": "New Orleans", "state": "LA", "dome": True},
    "New York Giants": {"venue": "MetLife Stadium", "city": "East Rutherford", "state": "NJ", "dome": False},
    "New York Jets": {"venue": "MetLife Stadium", "city": "East Rutherford", "state": "NJ", "dome": False},
    "Philadelphia Eagles": {"venue": "Lincoln Financial Field", "city": "Philadelphia", "state": "PA", "dome": False},
    "Pittsburgh Steelers": {"venue": "Acrisure Stadium", "city": "Pittsburgh", "state": "PA", "dome": False},
    "San Francisco 49ers": {"venue": "Levi's Stadium", "city": "Santa Clara", "state": "CA", "dome": False},
    "Seattle Seahawks": {"venue": "Lumen Field", "city": "Seattle", "state": "WA", "dome": False},
    "Tampa Bay Buccaneers": {"venue": "Raymond James Stadium", "city": "Tampa", "state": "FL", "dome": False},
    "Tennessee Titans": {"venue": "Nissan Stadium", "city": "Nashville", "state": "TN", "dome": False},
    "Washington Commanders": {"venue": "Northwest Stadium", "city": "Landover", "state": "MD", "dome": False},
}
