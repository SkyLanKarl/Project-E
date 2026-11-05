import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    (ROOT / "data/raw/cliopatria/cliopatria_polities_only_v021.geojson", "Wikidata"),
    (ROOT / "data/raw/natural-earth/geojson/ne_50m_admin_0_countries.geojson", "WIKIDATAID"),
)
OUTPUT = ROOT / "data/raw/wikidata/polity-dates.json"
API = "https://www.wikidata.org/w/api.php"


def collect_qids():
    qids = set()
    for path, field in SOURCES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as source_file:
            features = json.load(source_file)["features"]
        qids.update(
            feature["properties"].get(field, "")
            for feature in features
            if feature["properties"].get(field, "").startswith("Q")
        )
    return sorted(qids)


def save(entities, requested):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({
            "source": "Wikidata wbgetentities",
            "sourceUrl": "https://www.wikidata.org/",
            "license": "CC0 1.0",
            "licenseUrl": "https://www.wikidata.org/wiki/Wikidata:Copyright",
            "startProperty": "P571 (inception)",
            "endProperty": "P576 (dissolved, abolished or demolished date)",
            "reviewStatus": "pending",
            "requested": sorted(requested),
            "entities": entities,
        }, output_file, ensure_ascii=False, indent=2)


def claim_dates(claims, latest=False):
    values = []
    for claim in claims:
        if claim.get("rank") == "deprecated":
            continue
        snak = claim.get("mainsnak", {})
        if snak.get("datatype") != "time" or "datavalue" not in snak:
            continue
        value = snak["datavalue"]["value"]
        match = re.match(r"^([+-])(\d+)-", value.get("time", ""))
        if not match:
            continue
        year = int(match.group(2)) * (-1 if match.group(1) == "-" else 1)
        values.append({
            "date": value["time"],
            "year": year,
            "precision": value.get("precision"),
            "calendar": value.get("calendarmodel"),
            "rank": claim.get("rank"),
        })
    preferred = [value for value in values if value["rank"] == "preferred"]
    if preferred:
        values = preferred
    unique = list({(value["date"], value["precision"], value["calendar"]): value for value in values}.values())
    if not unique:
        return None
    selected = (max if latest else min)(unique, key=lambda value: (value["year"], value["date"]))
    return {
        **selected,
        "candidateYears": sorted({value["year"] for value in unique}),
        "candidates": unique,
    }


def main():
    qids = collect_qids()
    entities = {}
    requested = set()
    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
        entities = cache.get("entities", {})
        requested = set(cache.get("requested", []))
    session = requests.Session()
    session.headers["User-Agent"] = "ProjectE-HistoricalResearchPrototype/0.1 (local research use)"
    for offset in range(0, len(qids), 50):
        batch = qids[offset:offset + 50]
        if all(qid in requested for qid in batch):
            continue
        for attempt in range(5):
            response = None
            try:
                response = session.get(API, params={
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "claims",
                    "format": "json",
                    "formatversion": 2,
                }, timeout=90)
                response.raise_for_status()
                payload = response.json()
                if "error" in payload:
                    raise RuntimeError(payload["error"])
                for qid in batch:
                    claims = payload.get("entities", {}).get(qid, {}).get("claims", {})
                    entities[qid] = {
                        "start": claim_dates(claims.get("P571", [])),
                        "end": claim_dates(claims.get("P576", []), latest=True),
                    }
                requested.update(batch)
                save(entities, requested)
                break
            except (requests.RequestException, ValueError, RuntimeError):
                if attempt == 4:
                    raise
                retry_after = response.headers.get("Retry-After") if response is not None else None
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 5 * (2 ** attempt))
        print(f"Fetched {min(offset + 50, len(qids))}/{len(qids)} Wikidata IDs")
        time.sleep(1.5)
    with_dates = sum(1 for entity in entities.values() if entity.get("start") or entity.get("end"))
    print(f"Saved dates for {with_dates}/{len(qids)} entities to {OUTPUT}")


if __name__ == "__main__":
    main()
