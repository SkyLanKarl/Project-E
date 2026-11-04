import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/cliopatria/cliopatria_polities_only_v021.geojson"
OUTPUT = ROOT / "data/raw/wikidata/labels-zh.json"
API = "https://www.wikidata.org/w/api.php"


def save(entities, requested):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({
            "source": "Wikidata wbgetentities",
            "license": "CC0 1.0",
            "licenseUrl": "https://www.wikidata.org/wiki/Wikidata:Copyright",
            "requested": sorted(requested),
            "entities": entities,
        }, output_file, ensure_ascii=False, indent=2)


def main():
    with SOURCE.open(encoding="utf-8") as source_file:
        features = json.load(source_file)["features"]
    qids = sorted({
        feature["properties"].get("Wikidata", "")
        for feature in features
        if feature["properties"].get("Wikidata", "").startswith("Q")
    })
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
            try:
                response = session.get(API, params={
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels",
                    "languages": "zh-hans|zh-hant|zh",
                    "format": "json",
                    "formatversion": 2,
                }, timeout=60)
                response.raise_for_status()
                payload = response.json()
                if "error" in payload:
                    raise RuntimeError(payload["error"])
                for qid, entity in payload.get("entities", {}).items():
                    labels = entity.get("labels", {})
                    selected = labels.get("zh-hans") or labels.get("zh") or labels.get("zh-hant")
                    if selected:
                        entities[qid] = {"zh": selected["value"]}
                requested.update(batch)
                save(entities, requested)
                break
            except (requests.RequestException, ValueError, RuntimeError):
                if attempt == 4:
                    raise
                retry_after = response.headers.get("Retry-After") if "response" in locals() else None
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 5 * (2 ** attempt))
        print(f"Fetched {min(offset + 50, len(qids))}/{len(qids)} Wikidata IDs")
        time.sleep(1.5)
    missing = [qid for qid in qids if qid not in entities]
    for offset in range(0, len(missing), 50):
        batch = missing[offset:offset + 50]
        response = session.get(API, params={
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "sitelinks",
            "sitefilter": "zhwiki",
            "format": "json",
            "formatversion": 2,
        }, timeout=60)
        response.raise_for_status()
        for qid, entity in response.json().get("entities", {}).items():
            sitelink = entity.get("sitelinks", {}).get("zhwiki")
            if sitelink:
                entities[qid] = {"zh": sitelink["title"], "source": "zhwiki sitelink"}
        save(entities, requested)
        time.sleep(1.5)
    print(f"Saved {len(entities)} Chinese labels to {OUTPUT}; {len(qids) - len(entities)} IDs have no Chinese label")


if __name__ == "__main__":
    main()
