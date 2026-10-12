"""Fetch the REAL inputs RaktSetu uses and cache them under data/raw/.

Real inputs (all open, no API keys):
  1. Blood bank locations in Jaipur      -> OpenStreetMap via Overpass API (ODbL)
  2. Road travel times between them      -> OSRM public demo server (OSM road network)
  3. Daily weather for Jaipur, 2016-now  -> Open-Meteo historical archive (ERA5, CC-BY 4.0)

Run:  python data/fetch_real_data.py
The cached CSVs are committed, so the rest of the project runs offline.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import time
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).resolve().parent / "raw"
UA = {"User-Agent": "RaktSetu/1.0 (open-source hackathon project)"}

# Jaipur urban bounding box (south, west, north, east)
BBOX = (26.70, 75.60, 27.10, 76.05)
JAIPUR = (26.9124, 75.7873)

OVERPASS_QUERY = f"""[out:json][timeout:90];
(
  nwr["healthcare"="blood_donation"]{BBOX};
  nwr["healthcare"="blood_bank"]{BBOX};
  nwr["amenity"="blood_bank"]{BBOX};
  nwr["name"~"[Bb]lood [Bb]ank"]{BBOX};
);
out center tags;"""


OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def _overpass(query: str) -> dict:
    """Public Overpass servers are often busy: retry across mirrors."""
    last = None
    for attempt in range(3):
        for url in OVERPASS_MIRRORS:
            try:
                r = requests.post(url, data={"data": query}, headers=UA, timeout=180)
                if r.ok and "json" in r.headers.get("content-type", ""):
                    return r.json()
                last = f"{url}: HTTP {r.status_code}"
            except requests.RequestException as e:
                last = f"{url}: {e}"
            print(f"  retrying ({last})")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"All Overpass mirrors failed. Last error: {last}")


def fetch_blood_banks() -> pd.DataFrame:
    rows = []
    for e in _overpass(OVERPASS_QUERY)["elements"]:
        c = e.get("center", e)
        t = e["tags"]
        rows.append(
            {
                "osm_type": e["type"],
                "osm_id": e["id"],
                "name": t.get("name", "").strip(),
                "lat": round(c["lat"], 5),
                "lon": round(c["lon"], 5),
                "operator_type": t.get("operator:type", "unknown"),
            }
        )
    df = pd.DataFrame(rows)
    df = df[df["name"] != ""]
    # The same facility is sometimes mapped twice (node + building way): keep one per ~100 m.
    df = df.sort_values(["osm_type"]).reset_index(drop=True)  # prefer nodes
    keep = []
    for i, r in df.iterrows():
        if all(_haversine_km(r.lat, r.lon, df.loc[k, "lat"], df.loc[k, "lon"]) > 0.1 for k in keep):
            keep.append(i)
    return df.loc[keep].sort_values("osm_id").reset_index(drop=True)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def fetch_travel_matrix(banks: pd.DataFrame) -> pd.DataFrame:
    coords = ";".join(f"{lon},{lat}" for lat, lon in zip(banks.lat, banks.lon))
    url = f"https://router.project-osrm.org/table/v1/driving/{coords}?annotations=duration,distance"
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    d = r.json()
    rows = []
    for i, a in enumerate(banks.osm_id):
        for j, b in enumerate(banks.osm_id):
            rows.append(
                {
                    "from_osm_id": a,
                    "to_osm_id": b,
                    "drive_min": round(d["durations"][i][j] / 60, 1),
                    "drive_km": round(d["distances"][i][j] / 1000, 2),
                }
            )
    return pd.DataFrame(rows)


def fetch_weather(start="2016-01-01") -> pd.DataFrame:
    end = (dt.date.today() - dt.timedelta(days=2)).isoformat()
    params = {
        "latitude": JAIPUR[0],
        "longitude": JAIPUR[1],
        "start_date": start,
        "end_date": end,
        "daily": "precipitation_sum,temperature_2m_mean,temperature_2m_max,relative_humidity_2m_mean",
        "timezone": "Asia/Kolkata",
    }
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", params=params, headers=UA, timeout=180)
    r.raise_for_status()
    daily = r.json()["daily"]
    df = pd.DataFrame(daily).rename(
        columns={
            "time": "date",
            "precipitation_sum": "rain_mm",
            "temperature_2m_mean": "temp_mean_c",
            "temperature_2m_max": "temp_max_c",
            "relative_humidity_2m_mean": "humidity_pct",
        }
    )
    return df.dropna().reset_index(drop=True)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    print("Fetching blood banks from OpenStreetMap ...")
    banks = fetch_blood_banks()
    banks.to_csv(RAW / "blood_banks_jaipur_osm.csv", index=False)
    print(f"  {len(banks)} blood banks")

    print("Fetching road travel matrix from OSRM ...")
    tm = fetch_travel_matrix(banks)
    tm.to_csv(RAW / "travel_matrix_osrm.csv", index=False)
    print(f"  {len(tm)} origin-destination pairs")

    print("Fetching Jaipur daily weather from Open-Meteo ...")
    w = fetch_weather()
    w.to_csv(RAW / "weather_jaipur_openmeteo.csv", index=False)
    print(f"  {len(w)} days ({w.date.iloc[0]} to {w.date.iloc[-1]})")

    meta = {
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sources": {
            "blood_banks_jaipur_osm.csv": "OpenStreetMap contributors, via Overpass API. Licence: ODbL 1.0",
            "travel_matrix_osrm.csv": "OSRM demo server on OpenStreetMap road data. Licence: ODbL 1.0",
            "weather_jaipur_openmeteo.csv": "Open-Meteo historical weather API (ERA5 reanalysis). Licence: CC BY 4.0",
        },
        "overpass_query": OVERPASS_QUERY,
    }
    (RAW / "SOURCES.json").write_text(json.dumps(meta, indent=2))
    print("Done.")


if __name__ == "__main__":
    main()
