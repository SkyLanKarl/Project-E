import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WIKIDATA = ROOT / "data/raw/wikidata/polity-attributes.json"
WIKIPEDIA = ROOT / "data/raw/wikipedia/polity-infoboxes.json"
OUTPUT = ROOT / "data/raw/political-systems/government-history.json"


def time_values(claim, prop):
    return [
        {
            "date": value.get("date"),
            "precision": value.get("precision"),
            "calendar": value.get("calendar"),
        }
        for value in claim.get("qualifiers", {}).get(prop, [])
        if value.get("date")
    ]


def text_periods(value):
    groups = re.findall(r"\([^)]*\d[^)]*\)", value) or [value]
    periods = []
    for group in groups:
        lower = group.lower()
        ranges = re.findall(r"(\d{3,4})\s*(?:–|—|-|to)\s*(\d{3,4})", group, re.I)
        if ranges:
            for start, end in ranges:
                periods.append({"startYear": int(start), "endYear": int(end), "dateRole": "range"})
            continue
        years = re.findall(r"\d{3,4}", group)
        if not years:
            continue
        if re.search(r"\b(?:until|before|to)\b", lower):
            periods.append({"endYear": int(years[-1]), "dateRole": "end"})
        elif re.search(r"\b(?:from|since|after)\b", lower):
            periods.append({"startYear": int(years[0]), "dateRole": "start"})
        else:
            periods.append({"year": int(years[0]), "dateRole": "unspecified"})
    return periods


def wikipedia_entries(value):
    entries = []
    for token in re.split(r";", value):
        token = token.strip()
        if not token:
            continue
        periods = text_periods(token)
        government = re.sub(r"\([^)]*\d[^)]*\)", "", token).strip(" ,()")
        has_words = bool(re.search(r"[A-Za-z]", government))
        if has_words:
            entries.append({"governmentType": government, "periods": periods, "rawText": token})
        elif periods and entries:
            entries[-1]["periods"].extend(periods)
        elif periods:
            entries.append({"governmentType": "", "periods": periods, "rawText": token})
    return entries


def main():
    wikidata = json.loads(WIKIDATA.read_text(encoding="utf-8"))
    wikipedia = json.loads(WIKIPEDIA.read_text(encoding="utf-8"))["entities"]
    entities = {}
    for qid, source in wikidata["entities"].items():
        claims = source.get("governmentForm", [])
        wiki = wikipedia.get(qid, {})
        fields = wiki.get("infobox", {})
        government_text = fields.get("government_type", "")
        if not claims and not government_text:
            continue
        wikidata_records = []
        for claim in claims:
            value = claim.get("value", {})
            value_qid = value.get("id", "")
            wikidata_records.append({
                "statementId": claim.get("id"),
                "governmentType": {
                    "qid": value_qid,
                    "label": wikidata["labels"].get(value_qid, {}).get("label", value_qid),
                },
                "start": time_values(claim, "P580"),
                "end": time_values(claim, "P582"),
                "pointInTime": time_values(claim, "P585"),
                "qualifiers": claim.get("qualifiers", {}),
                "referenceUrls": claim.get("referenceUrls", []),
                "sourceUrl": f"https://www.wikidata.org/wiki/{qid}",
                "reviewStatus": "pending",
            })
        entities[qid] = {
            "wikipediaTitle": wiki.get("title"),
            "wikidata": wikidata_records,
            "wikipedia": {
                "title": wiki.get("title"),
                "url": wiki.get("url"),
                "revisionId": wiki.get("revisionId"),
                "rawText": government_text,
                "entries": wikipedia_entries(government_text),
                "reviewStatus": "pending",
            } if government_text else None,
        }
    output = {
        "title": "Political system and government-form history",
        "description": "Wikidata P122 statements and English Wikipedia infobox government_type text with date clues; research data only, not automatically reviewed history.",
        "sources": {
            "wikidata": {"url": "https://www.wikidata.org/", "license": "CC0 1.0", "property": "P122"},
            "wikipedia": {"url": "https://en.wikipedia.org/", "license": "CC BY-SA 4.0", "field": "government_type"},
        },
        "datePrecision": "Wikidata precision is preserved; Wikipedia parsed years require manual review.",
        "entities": entities,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(output, output_file, ensure_ascii=False, indent=2)
    wikidata_timed = sum(
        bool(record["start"] or record["end"] or record["pointInTime"])
        for entity in entities.values() for record in entity["wikidata"]
    )
    wikipedia_timed = sum(
        bool(entry["periods"])
        for entity in entities.values() if entity["wikipedia"]
        for entry in entity["wikipedia"]["entries"]
    )
    wikipedia_periods = sum(
        len(entry["periods"])
        for entity in entities.values() if entity["wikipedia"]
        for entry in entity["wikipedia"]["entries"]
    )
    print(f"Saved {len(entities)} entities to {OUTPUT}")
    print(f"Wikidata time-qualified records: {wikidata_timed}")
    print(f"Wikipedia entries with date clues: {wikipedia_timed}; periods: {wikipedia_periods}")


if __name__ == "__main__":
    main()
