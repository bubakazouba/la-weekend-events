"""
Fill drive_time_min (and refresh distance_miles) for every event in events.json
using Google Maps Distance Matrix API.

Usage:
  1. Save an API key (Distance Matrix API enabled) at:
       C:/Users/bubakazouba/chat-assistant/credentials/google_maps_key.txt
  2. python apply_drive_times.py

Departure time for drive-time estimate: next Saturday 11:00am local.
"""
import json, os, sys, datetime, urllib.parse, urllib.request

HOME = "1299 Cordova St, Pasadena, CA"
KEY_PATH = r"C:\Users\bubakazouba\chat-assistant\credentials\google_maps_key.txt"

def next_sat_11am_epoch():
    now = datetime.datetime.now()
    days_until_sat = (5 - now.weekday()) % 7 or 7
    sat = (now + datetime.timedelta(days=days_until_sat)).replace(hour=11, minute=0, second=0, microsecond=0)
    return int(sat.timestamp())

def fetch(key, origins, dests, dep):
    q = urllib.parse.urlencode({
        "origins": origins, "destinations": "|".join(dests),
        "departure_time": dep, "traffic_model": "best_guess",
        "units": "imperial", "key": key,
    })
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?{q}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())

def main():
    if not os.path.exists(KEY_PATH):
        print(f"No key at {KEY_PATH} — aborting.", file=sys.stderr)
        sys.exit(1)
    key = open(KEY_PATH).read().strip()

    with open("events.json", encoding="utf-8") as f:
        data = json.load(f)

    dep = next_sat_11am_epoch()

    # Build one big venue list across all weekends
    all_events = []
    for wk in data["weekends"]:
        for ev in wk.get("events", []) or []:
            all_events.append(ev)

    # Chunk to 25 destinations per request (API limit)
    for i in range(0, len(all_events), 25):
        chunk = all_events[i:i+25]
        dests = [ev["venue"] + ", Los Angeles, CA" for ev in chunk]
        resp = fetch(key, HOME, dests, dep)
        row = resp.get("rows", [{}])[0].get("elements", [])
        for ev, el in zip(chunk, row):
            if el.get("status") != "OK":
                print(f"SKIP {ev['id']} ({el.get('status')})")
                continue
            ev["distance_miles"] = round(el["distance"]["value"] / 1609.344, 1)
            # prefer duration_in_traffic when available
            dur = el.get("duration_in_traffic") or el["duration"]
            ev["drive_time_min"] = round(dur["value"] / 60)
            print(f"{ev['id']}: {ev['distance_miles']} mi / {ev['drive_time_min']} min")

    data["updated"] = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    data["distance_method"] = "driving miles + traffic-aware drive time via Google Distance Matrix (next Sat 11am departure)."
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("saved")

if __name__ == "__main__":
    main()
