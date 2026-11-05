import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/wikipedia/polity-infoboxes.json"
OUTPUT = ROOT / "data/raw/wikipedia/page-qid-audit.json"
API = "https://en.wikipedia.org/w/api.php"


def save(records, requested):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({"source": "English Wikipedia pageprops", "requested": sorted(requested), "records": records}, output_file, ensure_ascii=False, indent=2)


def request_batch(session, titles):
    for attempt in range(5):
        response = None
        try:
            response = session.get(API, params={
                "action": "query",
                "prop": "pageprops",
                "titles": "|".join(titles),
                "format": "json",
                "formatversion": 2,
            }, timeout=60)
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(payload["error"])
            return payload
        except (requests.RequestException, ValueError, RuntimeError):
            if attempt == 4:
                raise
            time.sleep(5 * (2 ** attempt))
    raise RuntimeError("Wikipedia audit request failed")


def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["entities"]
    records = {}
    requested = set()
    if OUTPUT.exists():
        cache = json.loads(OUTPUT.read_text(encoding="utf-8"))
        records = cache.get("records", {})
        requested = set(cache.get("requested", []))
    session = requests.Session()
    session.headers["User-Agent"] = "ProjectE-HistoricalResearchPrototype/0.1 (local research use)"
    qids = sorted(source)
    for offset in range(0, len(qids), 50):
        batch = qids[offset:offset + 50]
        if all(qid in requested for qid in batch):
            continue
        titles = [source[qid]["title"] for qid in batch if source[qid].get("title")]
        payload = request_batch(session, titles)
        by_title = {page["title"]: page for page in payload.get("query", {}).get("pages", [])}
        for qid in batch:
            title = source[qid].get("title")
            page = by_title.get(title, {})
            wikipedia_qid = page.get("pageprops", {}).get("wikibase_item")
            records[qid] = {
                "title": title,
                "expectedQid": qid,
                "wikipediaQid": wikipedia_qid,
                "match": qid == wikipedia_qid,
            }
        requested.update(batch)
        save(records, requested)
        print(f"Audited {min(offset + 50, len(qids))}/{len(qids)}", flush=True)
        time.sleep(1)
    mismatches = [record for record in records.values() if not record["match"]]
    print(f"Found {len(mismatches)} mismatches or missing QIDs in {len(records)} records")
    for record in mismatches:
        print(json.dumps(record, ensure_ascii=True))


if __name__ == "__main__":
    main()
