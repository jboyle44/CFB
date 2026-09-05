import requests, json
resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
    "latitude": 40.0016447,
    "longitude": -83.0197266,
    "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,weather_code",
    "temperature_unit": "fahrenheit",
    "wind_speed_unit": "mph",
    "forecast_days": 3,
    "timezone": "America/New_York",
}, timeout=20)
with open('../weather_diag.txt', 'w') as f:
    f.write(f"status={resp.status_code}\n")
    data = resp.json()
    f.write(json.dumps({k: (v[:5] if isinstance(v, list) else v) for k, v in data.get('hourly', {}).items()}, indent=2))
    f.write("\n\nTop-level keys: " + str(list(data.keys())))
