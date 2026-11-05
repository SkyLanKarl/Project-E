import html
import json
import re
import time
from pathlib import Path

import requests

from entity_identity import correct_qid, load_qid_overrides

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/raw/wikipedia/polity-infoboxes.json"
API = "https://en.wikipedia.org/w/api.php"
INFOBOX_PATTERN = re.compile(r"\{\{\s*(?:Infobox\s+(?:country|former country|former subdivision|colony|empire)|Infobox\s+settlement)\b", re.I)


def collect_pages():
    pages = {}
    overrides = load_qid_overrides()
    sources = (
        (ROOT / "data/raw/cliopatria/cliopatria_polities_only_v021.geojson", "Wikidata"),
        (ROOT / "prototype/data/modern-2024.geojson", "Wikidata"),
    )
    for path, qid_field in sources:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as source_file:
            features = json.load(source_file)["features"]
        for feature in features:
            properties = feature["properties"]
            qid = correct_qid(properties, overrides)
            title = properties.get("Wikipedia", "")
            if qid.startswith("Q") and title:
                pages[qid] = title.replace(" ", "_")
    return pages


def save(entities, requested):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({
            "source": "English Wikipedia infoboxes",
            "sourceUrl": "https://en.wikipedia.org/",
            "license": "CC BY-SA 4.0",
            "licenseUrl": "https://en.wikipedia.org/wiki/Wikipedia:Text_of_the_Creative_Commons_Attribution-ShareAlike_4.0_International_License",
            "reviewStatus": "pending",
            "requested": sorted(requested),
            "entities": entities,
        }, output_file, ensure_ascii=False, indent=2)


def split_top_level(value, delimiter="|"):
    parts = []
    start = 0
    template_depth = 0
    link_depth = 0
    index = 0
    while index < len(value):
        pair = value[index:index + 2]
        if pair == "{{":
            template_depth += 1
            index += 2
            continue
        if pair == "}}" and template_depth:
            template_depth -= 1
            index += 2
            continue
        if pair == "[[":
            link_depth += 1
            index += 2
            continue
        if pair == "]]" and link_depth:
            link_depth -= 1
            index += 2
            continue
        if value[index] == delimiter and not template_depth and not link_depth:
            parts.append(value[start:index])
            start = index + 1
        index += 1
    parts.append(value[start:])
    return parts


def extract_infobox(wikitext):
    match = INFOBOX_PATTERN.search(wikitext)
    if not match:
        return "", ""
    start = match.start()
    depth = 0
    index = start
    while index < len(wikitext) - 1:
        pair = wikitext[index:index + 2]
        if pair == "{{":
            depth += 1
            index += 2
            continue
        if pair == "}}":
            depth -= 1
            if not depth:
                raw = wikitext[start:index + 2]
                return match.group(0).strip("{} \n"), raw
            index += 2
            continue
        index += 1
    return "", ""


def template_text(template):
    content = template[2:-2]
    parts = split_top_level(content)
    name = parts[0].strip().lower().replace("_", " ")
    values = [part.strip() for part in parts[1:] if part.strip() and "=" not in part]
    if name in {"start date", "end date", "start date and age", "end date and age", "birth date", "death date"}:
        return values[0] if values else ""
    if name in {"start date and years", "end date and years"}:
        return values[0] if values else ""
    if name in {"convert", "significant figures"}:
        return " ".join(values[:3])
    if name in {"flag", "flagicon", "flagdeco", "flagcountry", "flaglink"}:
        return values[0] if values else ""
    if name in {"lang", "langx", "transliteration", "transl"}:
        return values[-1] if values else ""
    if name in {"ubl", "ublist", "plainlist", "flatlist", "unbulleted list", "bulletlist"}:
        return "; ".join(values)
    if name in {"nowrap", "nobr", "small", "smallcaps", "abbr", "linktext"}:
        return " ".join(values)
    if name in {"circa", "ca", "c.", "approximately"}:
        return "约" + (values[0] if values else "")
    if name in {"date", "year"}:
        return values[0] if values else ""
    return " ".join(values)


def clean_value(value):
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = re.sub(r"<ref\b[^>]*/>", "", value, flags=re.I)
    value = re.sub(r"<ref\b[^>]*>.*?</ref>", "", value, flags=re.I | re.S)
    value = re.sub(r"<br\s*/?>", "; ", value, flags=re.I)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\{\{[^{}]*\}\}", lambda match: template_text(match.group(0)), value)
    value = re.sub(r"\[\[(?:File|Image|Category):[^\]]*\]\]", "", value, flags=re.I)
    value = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", lambda match: match.group(2), value)
    value = re.sub(r"\[\[([^\]]*)\]\]", lambda match: match.group(1), value)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).replace("'''", "").replace("''", "")
    value = re.sub(r"^\s*[*#;:]+\s*", "", value, flags=re.M)
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\s*\n\s*", "; ", value)
    value = re.sub(r"\s*;\s*", "; ", value)
    return value.strip(" ;\n")


def parse_infobox(raw):
    if not raw:
        return {}
    content = raw[2:-2]
    fields = {}
    for part in split_top_level(content)[1:]:
        pair = split_top_level(part, "=")
        if len(pair) < 2:
            continue
        key = pair[0].strip().lower().replace(" ", "_")
        value = clean_value("=".join(pair[1:]))
        if key and value:
            fields[key] = value
    return fields


def request_batch(session, titles):
    for attempt in range(5):
        response = None
        try:
            response = session.get(API, params={
                "action": "query",
                "prop": "revisions",
                "rvprop": "content|ids",
                "rvslots": "main",
                "redirects": 1,
                "titles": "|".join(titles),
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
    raise RuntimeError("Wikipedia request failed")


def fetch_pages(session, pages, batch):
    payload = request_batch(session, [pages[qid] for qid in batch])
    aliases = {}
    for kind in ("normalized", "redirects"):
        for item in payload.get("query", {}).get(kind, []):
            aliases[item["from"].replace(" ", "_")] = item["to"].replace(" ", "_")
    by_title = {page["title"].replace(" ", "_"): page for page in payload.get("query", {}).get("pages", [])}
    result = {}
    for qid in batch:
        requested_title = pages[qid]
        title = requested_title
        seen = set()
        while title in aliases and title not in seen:
            seen.add(title)
            title = aliases[title]
        page = by_title.get(title, {})
        revision = page.get("revisions", [{}])[0]
        wikitext = revision.get("slots", {}).get("main", {}).get("content", "")
        infobox_type, raw = extract_infobox(wikitext)
        result[qid] = {
            "requestedTitle": requested_title,
            "title": page.get("title", title.replace("_", " ")),
            "pageId": page.get("pageid"),
            "revisionId": revision.get("revid"),
            "url": "https://en.wikipedia.org/wiki/" + page.get("title", title).replace(" ", "_"),
            "missing": bool(page.get("missing")),
            "infoboxType": infobox_type,
            "infobox": parse_infobox(raw),
        }
    return result


def main():
    pages = collect_pages()
    entities = {}
    requested = set()
    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
        entities = cache.get("entities", {})
        requested = set(cache.get("requested", []))
    session = requests.Session()
    session.headers["User-Agent"] = "ProjectE-HistoricalResearchPrototype/0.1 (local research use)"
    qids = sorted(pages)
    for offset in range(0, len(qids), 50):
        batch = qids[offset:offset + 50]
        if all(qid in requested for qid in batch):
            continue
        entities.update(fetch_pages(session, pages, batch))
        requested.update(batch)
        save(entities, requested)
        print(f"Fetched {min(offset + 50, len(qids))}/{len(qids)} Wikipedia entities", flush=True)
        time.sleep(1)
    with_infobox = sum(bool(entity.get("infobox")) for entity in entities.values())
    print(f"Saved {len(entities)} entities; {with_infobox} have infobox fields: {OUTPUT}")


if __name__ == "__main__":
    main()
