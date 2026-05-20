import json
from curl_cffi import requests

base_url = "https://api.sofascore.com/api/v1"
session = requests.Session()

# World Cup is tournament 16, season 41087
url = f"{base_url}/unique-tournament/16/season/41087/events/last/0"
try:
    resp = session.get(url, impersonate="chrome124", timeout=15)
    events = resp.json().get("events", [])
    for e in events:
        h = e.get("homeTeam", {}).get("name", "")
        a = e.get("awayTeam", {}).get("name", "")
        if "Argentina" in h and "France" in a:
            print(f"Match found! ID: {e['id']} - {h} vs {a}")
except Exception as ex:
    print("Error:", ex)
