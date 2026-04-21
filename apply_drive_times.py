"""
Fill drive_time_min (and refresh distance_miles) for every event in events.json
using Google Maps Platform **Routes API** (new).

Requires these APIs enabled on the GCP project:
  - Routes API
  - Billing (Maps Platform needs a billing account)

Usage:
  1. Save an API key at:
       C:/Users/bubakazouba/chat-assistant/credentials/google_maps_key.txt
  2. python apply_drive_times.py

Departure time: next Saturday 11:00am local — used for traffic-aware estimate.
"""
import json, os, sys, datetime, urllib.request

HOME = "1299 Cordova St, Pasadena, CA"
KEY_PATH = r"C:\Users\bubakazouba\chat-assistant\credentials\google_maps_key.txt"
ENDPOINT = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"

def next_sat_11am_utc():
    now = datetime.datetime.now().astimezone()
    days_until_sat = (5 - now.weekday()) % 7 or 7
    sat = (now + datetime.timedelta(days=days_until_sat)).replace(
        hour=11, minute=0, second=0, microsecond=0)
    return sat.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def compute_matrix(key, origins, destinations, departure):
    body = {
        "origins": [{"waypoint": {"address": o}} for o in origins],
        "destinations": [{"waypoint": {"address": d}} for d in destinations],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "departureTime": departure,
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,condition",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def main():
    if not os.path.exists(KEY_PATH):
        print(f"No key at {KEY_PATH} — aborting.", file=sys.stderr)
        sys.exit(1)
    key = open(KEY_PATH).read().strip()

    with open("events.json", encoding="utf-8") as f:
        data = json.load(f)

    departure = next_sat_11am_utc()
    print(f"Departure time for traffic estimate: {departure}")

    # Collect all events with a resolvable venue
    all_events = []
    for wk in data["weekends"]:
        for ev in wk.get("events", []) or []:
            if ev.get("venue"):
                all_events.append(ev)
    print(f"{len(all_events)} events to process")

    # Chunk: Routes API allows up to 625 element pairs per request.
    # With 1 origin that's 625 destinations per call — well within.
    dests = [ev["venue"] + ", Los Angeles, CA" for ev in all_events]
    results = compute_matrix(key, [HOME], dests, departure)

    by_idx = {r["destinationIndex"]: r for r in results}
    for i, ev in enumerate(all_events):
        r = by_idx.get(i)
        if not r:
            print(f"SKIP {ev['id']} (no result)")
            continue
        if "distanceMeters" in r and "duration" in r:
            ev["distance_miles"] = round(r["distanceMeters"] / 1609.344, 1)
            # duration comes as "1234s" — strip the s
            secs = int(r["duration"].rstrip("s"))
            ev["drive_time_min"] = round(secs / 60)
            print(f"{ev['id']}: {ev['distance_miles']} mi / {ev['drive_time_min']} min")
        else:
            print(f"SKIP {ev['id']} (cond={r.get('condition')})")

    data["updated"] = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    data["distance_method"] = "driving miles + traffic-aware drive time via Google Routes API (next Sat 11am local departure)."
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("saved")

if __name__ == "__main__":
    main()
