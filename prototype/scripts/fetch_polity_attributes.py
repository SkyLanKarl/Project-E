import json
import time
from decimal import Decimal
from pathlib import Path

import requests

from fetch_polity_dates import collect_qids

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/raw/wikidata/polity-attributes.json"
API = "https://www.wikidata.org/w/api.php"
PROPERTIES = {
    "capital": "P36",
    "population": "P1082",
    "officialLanguage": "P37",
    "religion": "P140",
    "currency": "P38",
    "governmentForm": "P122",
    "headOfState": "P35",
    "headOfGovernment": "P6",
    "area": "P2046",
    "predecessor": "P155",
    "successor": "P156",
    "entityType": "P31",
    "partOf": "P361",
    "hasParts": "P527",
    "administrativeDivisions": "P150",
    "diplomaticRelations": "P530",
    "memberOf": "P463",
}
RELATED_PROPERTIES = {
    "capitalCoordinates": "P625",
    "positionsHeld": "P39",
}


def save(entities, requested, related_entities, related_requested, labels, labels_requested):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({
            "source": "Wikidata wbgetentities",
            "sourceUrl": "https://www.wikidata.org/",
            "license": "CC0 1.0",
            "licenseUrl": "https://www.wikidata.org/wiki/Wikidata:Copyright",
            "reviewStatus": "pending",
            "properties": PROPERTIES,
            "relatedProperties": RELATED_PROPERTIES,
            "qualifierProperties": "All qualifiers are retained by Wikidata property ID",
            "referenceProperty": "P854 (reference URL)",
            "requested": sorted(requested),
            "entities": entities,
            "relatedRequested": sorted(related_requested),
            "relatedEntities": related_entities,
            "labelsRequested": sorted(labels_requested),
            "labels": labels,
        }, output_file, ensure_ascii=False, indent=2)


def normalize_snak(snak):
    if "datavalue" not in snak:
        return {"snaktype": snak.get("snaktype")}
    value = snak["datavalue"]["value"]
    datatype = snak.get("datatype")
    if datatype == "wikibase-item":
        return {"id": value["id"]}
    if datatype == "quantity":
        amount = Decimal(value["amount"])
        return {
            "amount": int(amount) if amount == amount.to_integral_value() else float(amount),
            "rawAmount": value["amount"],
            "unit": value.get("unit"),
        }
    if datatype == "time":
        return {
            "date": value.get("time"),
            "precision": value.get("precision"),
            "calendar": value.get("calendarmodel"),
        }
    if datatype == "monolingualtext":
        return {"text": value.get("text"), "language": value.get("language")}
    if datatype == "globe-coordinate":
        return {
            "latitude": value.get("latitude"),
            "longitude": value.get("longitude"),
            "altitude": value.get("altitude"),
            "globe": value.get("globe"),
        }
    return {"value": value}


def reference_urls(claim):
    urls = []
    for reference in claim.get("references", []):
        for snak in reference.get("snaks", {}).get("P854", []):
            value = snak.get("datavalue", {}).get("value")
            if isinstance(value, str):
                urls.append(value)
    return sorted(set(urls))


def normalize_claim(claim):
    qualifiers = {
        prop: [normalize_snak(snak) for snak in snaks]
        for prop, snaks in claim.get("qualifiers", {}).items()
    }
    return {
        "id": claim.get("id"),
        "rank": claim.get("rank"),
        "value": normalize_snak(claim.get("mainsnak", {})),
        "qualifiers": qualifiers,
        "referenceUrls": reference_urls(claim),
    }


def claim_item_ids(claim):
    ids = set()
    value = claim["value"]
    if value.get("id"):
        ids.add(value["id"])
    unit = value.get("unit", "")
    if unit.startswith("http") and unit.rsplit("/", 1)[-1].startswith("Q"):
        ids.add(unit.rsplit("/", 1)[-1])
    for prop in ("P518", "P1001", "P1480"):
        for value in claim["qualifiers"].get(prop, []):
            if value.get("id"):
                ids.add(value["id"])
    return ids


def request_batch(session, params):
    for attempt in range(5):
        response = None
        try:
            response = session.get(API, params={
                **params,
                "format": "json",
                "formatversion": 2,
            }, timeout=90)
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(payload["error"])
            return payload
        except (requests.RequestException, ValueError, RuntimeError):
            if attempt == 4:
                raise
            retry_after = response.headers.get("Retry-After") if response is not None else None
            time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 5 * (2 ** attempt))
    raise RuntimeError("Wikidata request failed")


def main():
    qids = collect_qids()
    entities = {}
    requested = set()
    related_entities = {}
    related_requested = set()
    labels = {}
    labels_requested = set()
    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
        entities = cache.get("entities", {})
        requested = set(cache.get("requested", []))
        related_entities = cache.get("relatedEntities", {})
        related_requested = set(cache.get("relatedRequested", []))
        labels = cache.get("labels", {})
        labels_requested = set(cache.get("labelsRequested", []))
    session = requests.Session()
    session.headers["User-Agent"] = "ProjectE-HistoricalResearchPrototype/0.1 (local research use)"
    for offset in range(0, len(qids), 50):
        batch = qids[offset:offset + 50]
        if all(
            qid in requested and all(name in entities.get(qid, {}) for name in PROPERTIES)
            for qid in batch
        ):
            continue
        payload = request_batch(session, {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "claims",
        })
        for qid in batch:
            claims = payload.get("entities", {}).get(qid, {}).get("claims", {})
            entities[qid] = {
                name: [
                    normalize_claim(claim)
                    for claim in claims.get(prop, [])
                    if claim.get("rank") != "deprecated"
                ]
                for name, prop in PROPERTIES.items()
            }
        requested.update(batch)
        save(entities, requested, related_entities, related_requested, labels, labels_requested)
        print(f"Fetched attributes for {min(offset + 50, len(qids))}/{len(qids)} entities", flush=True)
        time.sleep(1.5)
    capital_qids = {
        claim["value"]["id"]
        for entity in entities.values()
        for claim in entity.get("capital", [])
        if claim["value"].get("id")
    }
    leader_qids = {
        claim["value"]["id"]
        for entity in entities.values()
        for field in ("headOfState", "headOfGovernment")
        for claim in entity.get(field, [])
        if claim["value"].get("id")
    }
    related_qids = sorted(capital_qids | leader_qids)
    for offset in range(0, len(related_qids), 50):
        batch = related_qids[offset:offset + 50]
        if all(qid in related_requested for qid in batch):
            continue
        payload = request_batch(session, {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "claims",
        })
        for qid in batch:
            claims = payload.get("entities", {}).get(qid, {}).get("claims", {})
            related_entities[qid] = {
                "capitalCoordinates": [
                    normalize_claim(claim)
                    for claim in claims.get("P625", [])
                    if claim.get("rank") != "deprecated"
                ] if qid in capital_qids else [],
                "positionsHeld": [
                    normalize_claim(claim)
                    for claim in claims.get("P39", [])
                    if claim.get("rank") != "deprecated"
                ] if qid in leader_qids else [],
            }
        related_requested.update(batch)
        save(entities, requested, related_entities, related_requested, labels, labels_requested)
        print(f"Fetched related data for {min(offset + 50, len(related_qids))}/{len(related_qids)} entities", flush=True)
        time.sleep(1.5)
    value_qids = sorted({
        qid
        for group in (entities, related_entities)
        for entity in group.values()
        for claims in entity.values()
        for claim in claims
        for qid in claim_item_ids(claim)
    })
    for offset in range(0, len(value_qids), 50):
        batch = value_qids[offset:offset + 50]
        if all(qid in labels_requested for qid in batch):
            continue
        payload = request_batch(session, {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels",
            "languages": "zh-hans|zh-hant|zh|en",
        })
        for qid in batch:
            entity_labels = payload.get("entities", {}).get(qid, {}).get("labels", {})
            zh = entity_labels.get("zh-hans") or entity_labels.get("zh") or entity_labels.get("zh-hant")
            en = entity_labels.get("en")
            selected = zh or en
            labels[qid] = {
                "zh": zh["value"] if zh else "",
                "en": en["value"] if en else "",
                "label": selected["value"] if selected else qid,
                "language": selected["language"] if selected else "",
            }
        labels_requested.update(batch)
        save(entities, requested, related_entities, related_requested, labels, labels_requested)
        print(f"Fetched labels for {min(offset + 50, len(value_qids))}/{len(value_qids)} related entities", flush=True)
        time.sleep(1.5)
    print(f"Saved {len(entities)} entities, {len(related_entities)} related entities and {len(labels)} labels to {OUTPUT}")


if __name__ == "__main__":
    main()
