"""
Fetches real weather forecasts (via Open-Meteo, free, no API key needed:
https://open-meteo.com) for outdoor games in this week's Games of the Week
list -- the same Top 10 CFB / Top 5 NFL selection shown on
games_of_week.html, not every game across the full slate, since most games
aren't featured there anyway.

Intentionally NOT run on the same weekly Tuesday cadence as everything
else on this site -- a forecast made 5+ days out is much less reliable
than one made closer to kickoff. Meant to run Thursday mornings, close to
the bulk of that week's games (Thu/Fri/Sat/Sun/Mon).

Only fetches for outdoor (dome=False) games with valid coordinates --
domed/indoor games don't need a forecast, and neither do those we don't
have a real venue location for.

Usage: python fetch_games_weather.py [output_path]
"""
import sys
import json
import datetime
import requests

SPREAD_WEIGHT = 1.0


def load_games(path):
    try:
        with open(path) as f:
            raw = json.load(f)
        return raw.get("games", []) if isinstance(raw, dict) else raw
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def current_week(games):
    """Mirrors the identical logic in games_of_week.html's JS -- the
    earliest week with any non-final game, or the latest week overall if
    every game this season is already final."""
    upcoming_weeks = [g["week"] for g in games if g.get("status") != "final"]
    if upcoming_weeks:
        return min(upcoming_weeks)
    all_weeks = [g["week"] for g in games]
    return max(all_weeks) if all_weeks else None


def game_score(g):
    """Mirrors the identical scoring formula in games_of_week.html's JS."""
    combined = (g.get("homeRating") or 0) + (g.get("awayRating") or 0)
    spread = g.get("vegasSpread")
    if spread is None:
        spread = g.get("modelSpread") or 0
    return combined - SPREAD_WEIGHT * abs(spread)


def top_games(games, count):
    week = current_week(games)
    this_week = [g for g in games if g.get("week") == week]
    return sorted(this_week, key=game_score, reverse=True)[:count]


def fetch_forecast_for_hour(lat, lon, target_iso):
    """Returns the forecast for the single hour closest to target_iso, or
    None if the game is too far in the future for Open-Meteo's forecast
    window (currently ~16 days) or the request otherwise fails."""
    try:
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": 16,
            "timezone": "UTC",
        }, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  forecast request failed: {e}", file=sys.stderr)
        return None

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return None

    target = target_iso[:13]  # "YYYY-MM-DDTHH" -- match to the hour
    try:
        idx = next(i for i, t in enumerate(times) if t.startswith(target))
    except StopIteration:
        return None  # game is outside the forecast window

    return {
        "temperatureF": hourly.get("temperature_2m", [None] * len(times))[idx],
        "precipitationProbability": hourly.get("precipitation_probability", [None] * len(times))[idx],
        "windSpeedMph": hourly.get("wind_speed_10m", [None] * len(times))[idx],
        "weatherCode": hourly.get("weather_code", [None] * len(times))[idx],
    }


def build(cfb_lines_path, nfl_lines_path, output_path):
    cfb_games = load_games(cfb_lines_path)
    nfl_games = load_games(nfl_lines_path)

    featured = top_games(cfb_games, 10) + top_games(nfl_games, 5)

    weather_by_game_id = {}
    for g in featured:
        if g.get("dome"):
            continue  # no forecast needed for indoor games
        lat, lon = g.get("venueLat"), g.get("venueLon")
        if lat is None or lon is None:
            continue  # no known coordinates for this venue
        forecast = fetch_forecast_for_hour(lat, lon, g["startDate"])
        if forecast:
            weather_by_game_id[str(g["gameId"])] = forecast

    wrapped = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "weather": weather_by_game_id,
    }

    with open(output_path, "w") as f:
        json.dump(wrapped, f, indent=2)
    print(f"Wrote weather for {len(weather_by_game_id)} of {len(featured)} featured games to {output_path}",
          file=sys.stderr)

    return wrapped


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python fetch_games_weather.py <cfb_lines_path> <nfl_lines_path> <output_path>",
              file=sys.stderr)
        sys.exit(1)
    build(sys.argv[1], sys.argv[2], sys.argv[3])
