import hashlib
import json
import re
import shutil
from pathlib import Path

from entity_identity import correct_qid, load_qid_overrides

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/cliopatria/cliopatria_polities_only_v021.geojson"
LICENSE = ROOT / "data/raw/cliopatria/LICENSE.md"
OUTPUT_DIR = ROOT / "prototype/data"
OUTPUT = OUTPUT_DIR / "cliopatria.geojson"


def round_coordinates(value):
    if isinstance(value, list):
        return [round_coordinates(item) for item in value]
    if isinstance(value, (int, float)):
        return round(value, 4)
    return value


def color_index(name):
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return digest[0] % 12


def label_point(geometry):
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    def polygon_span(polygon):
        ring = polygon[0]
        xs = [point[0] for point in ring]
        ys = [point[1] for point in ring]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))
    def point_in_ring(point, ring):
        x, y = point
        inside = False
        previous = ring[-1]
        for current in ring:
            x1, y1 = previous[:2]
            x2, y2 = current[:2]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
            previous = current
        return inside
    polygon = max(polygons, key=polygon_span)
    ring = polygon[0]
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    candidates = [
        [(min_x + max_x) / 2, (min_y + max_y) / 2],
        [sum(xs) / len(xs), sum(ys) / len(ys)],
    ]
    candidates.extend(
        [min_x + (max_x - min_x) * column / 12, min_y + (max_y - min_y) * row / 12]
        for row in range(1, 12)
        for column in range(1, 12)
    )
    for point in candidates:
        if point_in_ring(point, ring) and not any(point_in_ring(point, hole) for hole in polygon[1:]):
            return [round(point[0], 4), round(point[1], 4)]
    return [round(ring[0][0], 4), round(ring[0][1], 4)]


def prepare_base_data():
    source_dir = ROOT / "data/raw/natural-earth/geojson"
    output_dir = OUTPUT_DIR / "natural-earth"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("land", "lakes", "rivers_lake_centerlines", "coastline"):
        source_path = source_dir / f"ne_50m_{name}.geojson"
        with source_path.open(encoding="utf-8") as source_file:
            source = json.load(source_file)
        features = [{
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": round_coordinates(feature["geometry"]["coordinates"]),
            },
        } for feature in source["features"]]
        output_path = output_dir / f"{name}.geojson"
        with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
            json.dump(
                {"type": "FeatureCollection", "features": features},
                output_file,
                separators=(",", ":"),
                allow_nan=False,
            )
        print(f"Wrote {len(features)} base features to {output_path}")
    shutil.copyfile(
        ROOT / "data/raw/natural-earth/terms-of-use.html",
        output_dir / "terms-of-use.html",
    )


def load_json(path):
    with path.open(encoding="utf-8") as source_file:
        return json.load(source_file)


def merge_wikipedia_dates(polity_dates, wikipedia):
    merged = json.loads(json.dumps(polity_dates))
    for qid, entity in wikipedia.items():
        fields = entity.get("infobox", {})
        if not fields:
            continue
        target = merged.setdefault(qid, {"start": None, "end": None})
        lifespan = re.findall(r"\d{1,4}", fields.get("life_span", ""))
        start_year = wikipedia_year(fields.get("year_start")) or (int(lifespan[0]) if lifespan else None)
        end_year = (wikipedia_year(fields.get("year_end")) or (int(lifespan[1]) if len(lifespan) > 1 else None)) if fields.get("year_start") or lifespan else None
        for key, year in (("start", start_year), ("end", end_year)):
            if target.get(key) or year is None:
                continue
            target[key] = {
                "date": f"{year:+d}-00-00T00:00:00Z",
                "year": year,
                "precision": 9,
                "candidateYears": [year],
                "source": "Wikipedia",
                "sourceUrl": entity.get("url"),
                "revisionId": entity.get("revisionId"),
                "license": "CC BY-SA 4.0",
            }
    return merged


def polity_date_properties(qid, polity_dates):
    entity = polity_dates.get(qid, {})
    start = entity.get("start") or {}
    end = entity.get("end") or {}
    has_dates = bool(start or end)
    sources = list(dict.fromkeys(
        value.get("source", "Wikidata") for value in (start, end) if value
    ))
    return {
        "PolityFromYear": start.get("year"),
        "PolityToYear": end.get("year"),
        "PolityFromDate": start.get("date"),
        "PolityToDate": end.get("date"),
        "PolityFromPrecision": start.get("precision"),
        "PolityToPrecision": end.get("precision"),
        "PolityDateSource": " / ".join(sources),
        "PolityDateReview": "pending" if has_dates else "missing",
        "PolityDateMultiple": bool(
            len(start.get("candidateYears", [])) > 1 or len(end.get("candidateYears", [])) > 1
        ),
    }


def prepare_feature(feature, index, labels, overrides, polity_dates, qid_overrides):
    properties = feature["properties"]
    name = properties["Name"]
    qid = correct_qid(properties, qid_overrides)
    name_zh = overrides.get(name) or labels.get(qid, {}).get("zh") or name
    role = "composite" if properties.get("Components") else "member" if properties.get("MemberOf") else "polity"
    return {
        "type": "Feature",
        "id": index,
        "properties": {
            "id": index,
            "Name": name,
            "NameZh": name_zh,
            "NameReview": "override" if name in overrides else "wikidata" if qid in labels else "pending",
            "FromYear": properties["FromYear"],
            "ToYear": properties["ToYear"],
            "Area": round(properties.get("Area") or 0, 1),
            "Wikipedia": properties.get("Wikipedia") or "",
            "Wikidata": qid,
            **polity_date_properties(qid, polity_dates),
            "MemberOf": properties.get("MemberOf") or "",
            "Components": properties.get("Components") or "",
            "role": role,
            "GeometryStatus": "source",
            "SourceFromYear": properties["FromYear"],
            "SourceToYear": properties["ToYear"],
            "ReviewStatus": "source",
            "LabelPoint": label_point(feature["geometry"]),
            "LabelPriority": properties.get("Area") or 0,
            "color": color_index(name),
        },
        "geometry": {
            "type": feature["geometry"]["type"],
            "coordinates": round_coordinates(feature["geometry"]["coordinates"]),
        },
    }


def wgs84_to_gcj02(lon, lat):
    import math
    if not (73.66 < lon < 135.05 and 3.86 < lat < 53.55):
        return lon, lat
    a = 6378245.0
    ee = 0.00669342162296594323
    x = lon - 105.0
    y = lat - 35.0
    dlat = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    dlat += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    dlat += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    dlat += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    dlon = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    dlon += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    dlon += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    dlon += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    radlat = lat / 180.0 * math.pi
    magic = 1 - ee * math.sin(radlat) ** 2
    sqrt_magic = math.sqrt(magic)
    dlat = dlat * 180.0 / ((a * (1 - ee)) / (magic * sqrt_magic) * math.pi)
    dlon = dlon * 180.0 / (a / sqrt_magic * math.cos(radlat) * math.pi)
    return lon + dlon, lat + dlat


def gcj02_to_wgs84(lon, lat):
    wgs_lon, wgs_lat = lon, lat
    for _ in range(4):
        converted_lon, converted_lat = wgs84_to_gcj02(wgs_lon, wgs_lat)
        wgs_lon -= converted_lon - lon
        wgs_lat -= converted_lat - lat
    return [wgs_lon, wgs_lat]


def convert_geometry_coordinates(value):
    if isinstance(value, list) and len(value) >= 2 and isinstance(value[0], (int, float)):
        return gcj02_to_wgs84(value[0], value[1])
    return [convert_geometry_coordinates(item) for item in value]


def prepare_modern_data(polity_dates):
    natural_earth = load_json(ROOT / "data/raw/natural-earth/geojson/ne_50m_admin_0_countries.geojson")
    world_bank = load_json(ROOT / "data/raw/world-bank-boundaries/WB_Boundaries_GeoJSON_highres/WB_countries_Admin0.geojson")
    natural_qids = {
        feature["properties"].get("NAME_EN"): feature["properties"].get("WIKIDATAID") or ""
        for feature in natural_earth["features"]
    }
    source_entries = [("World Bank", feature) for feature in world_bank["features"]]
    source_entries.extend(
        ("Natural Earth", feature) for feature in natural_earth["features"]
        if feature["properties"].get("NAME_EN") == "Taiwan"
    )
    features = []
    for source_name, feature in source_entries:
        properties = feature["properties"]
        name = properties.get("NAME_EN") or properties["NAME"]
        if name in {"People's Republic of China", "Hong Kong", "Macau", "Siachen Glacier", "Antarctica"} or properties.get("WIKIDATAID") in {"Q148", "Q8646", "Q14773", "Q333946", "Q51"}:
            continue
        sovereignty = properties.get("SOVEREIGNT") or name
        is_member = properties.get("TYPE") not in {"Sovereign country", "Country"} and sovereignty != name
        feature_id = len(features)
        qid = properties.get("WIKIDATAID") or natural_qids.get(name, "")
        features.append({
            "type": "Feature",
            "id": feature_id,
            "properties": {
                "id": feature_id,
                "Name": name,
                "NameZh": properties.get("NAME_ZH") or name,
                "NameReview": "world-bank" if source_name == "World Bank" else "natural-earth",
                "FromYear": 2024,
                "ToYear": 2024,
                "Area": 0,
                "Wikipedia": name,
                "Wikidata": qid,
                **polity_date_properties(qid, polity_dates),
                "MemberOf": f"({sovereignty})" if is_member else "",
                "Components": "",
                "role": "member" if is_member else "polity",
                "GeometryStatus": "reference",
                "SourceFromYear": 2024,
                "SourceToYear": 2024,
                "ReviewStatus": "pending",
                "Type": properties.get("TYPE") or "",
                "Sovereignty": sovereignty,
                "Source": source_name,
                "LabelPoint": label_point(feature["geometry"]),
                "LabelPriority": properties.get("POP_EST") or 0,
                "color": color_index(name),
            },
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": round_coordinates(feature["geometry"]["coordinates"]),
            },
        })
    china = load_json(ROOT / "data/raw/aliyun-datav/100000_full.json")
    for feature in china["features"]:
        properties = feature["properties"]
        if properties.get("adcode") in {710000, "100000_JD"}:
            continue
        name = properties["name"]
        feature_id = len(features)
        center = properties.get("centroid") or properties["center"]
        features.append({
            "type": "Feature",
            "id": feature_id,
            "properties": {
                "id": feature_id,
                "Name": name,
                "NameZh": name,
                "NameReview": "datav",
                "FromYear": 2024,
                "ToYear": 2024,
                "Area": 0,
                "Wikipedia": "",
                "Wikidata": "",
                **polity_date_properties("", polity_dates),
                "MemberOf": "",
                "Components": "",
                "role": "admin-province",
                "GeometryStatus": "reference",
                "SourceFromYear": 2024,
                "SourceToYear": 2024,
                "ReviewStatus": "pending",
                "Type": "province",
                "Sovereignty": "People's Republic of China",
                "Source": "DataV",
                "LabelPoint": gcj02_to_wgs84(*center),
                "LabelPriority": 1,
                "LabelMinZoom": 4,
                "color": color_index("People's Republic of China"),
            },
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": convert_geometry_coordinates(feature["geometry"]["coordinates"]),
            },
        })
    output = OUTPUT_DIR / "modern-2024.geojson"
    with output.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            output_file,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    print(f"Wrote {len(features)} pending-review modern features to {output}")


def wikipedia_claim(entity, key, value, qualifiers=None):
    return {
        "id": f"wikipedia:{entity.get('revisionId')}:{key}",
        "rank": "normal",
        "value": value,
        "qualifiers": qualifiers or {},
        "referenceUrls": [entity["url"]] if entity.get("url") else [],
        "source": "Wikipedia",
        "sourceUrl": entity.get("url"),
        "revisionId": entity.get("revisionId"),
        "license": "CC BY-SA 4.0",
    }


def wikipedia_year(value):
    match = re.search(r"\d{1,4}", value or "")
    if not match:
        return None
    year = int(match.group(0))
    return -year if re.search(r"\b(?:BC|BCE)\b", value, re.I) else year


def wikipedia_time_qualifier(year):
    if year is None:
        return {}
    return {"P585": [{"date": f"{year:+d}-00-00T00:00:00Z", "precision": 9}]}


def wikipedia_quantity(entity, keys, year_keys, unit):
    fields = entity.get("infobox", {})
    for key in keys:
        value = fields.get(key, "")
        match = re.search(r"-?\d[\d, ]*(?:\.\d+)?", value)
        if not match:
            continue
        raw = match.group(0).replace(",", "").replace(" ", "")
        try:
            amount = float(raw)
        except ValueError:
            continue
        year = next((wikipedia_year(fields.get(y)) for y in year_keys if fields.get(y)), None)
        return wikipedia_claim(entity, key, {
            "amount": int(amount) if amount.is_integer() else amount,
            "rawAmount": raw,
            "unit": unit,
        }, wikipedia_time_qualifier(year))
    return None


def merge_wikipedia_attributes(source, wikipedia):
    entities = json.loads(json.dumps(source.get("entities", {})))
    field_keys = {
        "capital": ["capital"],
        "officialLanguage": ["official_languages"],
        "religion": ["religion"],
        "currency": ["currency"],
        "governmentForm": ["government_type"],
        "headOfState": ["leader1", "leader_name1"],
        "headOfGovernment": ["deputy1"],
        "entityType": ["status"],
        "memberOf": ["membership"],
    }
    added = 0
    for qid, entity in wikipedia.items():
        if not entity.get("infobox"):
            continue
        target = entities.setdefault(qid, {name: [] for name in source.get("properties", {})})
        for field, keys in field_keys.items():
            if target.get(field):
                continue
            for key in keys:
                value = entity["infobox"].get(key)
                if not value:
                    continue
                qualifiers = {}
                year_key = {"leader1": "year_leader1", "deputy1": "year_deputy1"}.get(key)
                years = re.findall(r"\d{3,4}", entity["infobox"].get(year_key, "")) if year_key else []
                if years:
                    qualifiers["P580"] = [{"date": f"{int(years[0]):+d}-00-00T00:00:00Z", "precision": 9}]
                if len(years) > 1:
                    qualifiers["P582"] = [{"date": f"{int(years[1]):+d}-00-00T00:00:00Z", "precision": 9}]
                target[field] = [wikipedia_claim(entity, key, {"text": value}, qualifiers)]
                added += 1
                break
        for field, prefix in (("predecessor", "p"), ("successor", "s")):
            if target.get(field):
                continue
            claims = [
                wikipedia_claim(entity, key, {"text": value})
                for key, value in entity["infobox"].items()
                if re.fullmatch(rf"{prefix}\d+", key) and value
            ]
            if claims:
                target[field] = claims
                added += 1
        if not target.get("population"):
            claim = wikipedia_quantity(
                entity,
                ["population_estimate", "population_census", "stat_pop1"],
                ["population_estimate_year", "population_census_year", "stat_year1"],
                "1",
            )
            if claim:
                target["population"] = [claim]
                added += 1
        if not target.get("area"):
            claim = wikipedia_quantity(
                entity,
                ["area_km2", "stat_area1"],
                ["stat_year1"],
                "http://www.wikidata.org/entity/Q712226",
            )
            if claim:
                target["area"] = [claim]
                added += 1
    return entities, added


def prepare_polity_attributes():
    source_path = ROOT / "data/raw/wikidata/polity-attributes.json"
    source = load_json(source_path) if source_path.exists() else {}
    wikipedia_path = ROOT / "data/raw/wikipedia/polity-infoboxes.json"
    wikipedia = load_json(wikipedia_path)["entities"] if wikipedia_path.exists() else {}
    entities, added = merge_wikipedia_attributes(source, wikipedia)
    output = OUTPUT_DIR / "polity-attributes.json"
    with output.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({
            "source": "Wikidata with Wikipedia missing-field fallback",
            "sourceUrl": "https://www.wikidata.org/ and https://en.wikipedia.org/",
            "license": "Wikidata CC0 1.0; Wikipedia CC BY-SA 4.0",
            "licenseUrl": "https://www.wikidata.org/wiki/Wikidata:Copyright and https://en.wikipedia.org/wiki/Wikipedia:Text_of_the_Creative_Commons_Attribution-ShareAlike_4.0_International_License",
            "reviewStatus": "pending",
            "properties": source.get("properties", {}),
            "relatedProperties": source.get("relatedProperties", {}),
            "entities": entities,
            "relatedEntities": source.get("relatedEntities", {}),
            "labels": source.get("labels", {}),
        }, output_file, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    print(f"Added {added} Wikipedia fallback fields; wrote {len(entities)} attributed entities to {output}")


def prepare_world_bank_disputed():
    source = load_json(ROOT / "data/raw/world-bank-boundaries/WB_Boundaries_GeoJSON_highres/WB_Admin0_disputed_areas.geojson")
    features = []
    for index, feature in enumerate(source["features"]):
        properties = feature["properties"]
        name = (properties.get("NAME_EN") or "").strip() or "Unnamed disputed area"
        name_zh = (properties.get("NAME_ZH") or "").strip() or "未命名争议区域"
        features.append({
            "type": "Feature",
            "id": -index - 2,
            "properties": {
                "id": -index - 2,
                "Name": name,
                "NameZh": name_zh,
                "NameReview": "world-bank",
                "FromYear": 2024,
                "ToYear": 2024,
                "Area": 0,
                "Wikipedia": name,
                "Wikidata": (properties.get("WIKIDATAID") or "").strip(),
                "MemberOf": "",
                "Components": "",
                "role": "disputed",
                "GeometryStatus": "disputed",
                "ReviewStatus": "source",
                "Source": "World Bank",
                "WbRules": properties.get("WB_RULES") or "",
            },
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": round_coordinates(feature["geometry"]["coordinates"]),
            },
        })
    output = OUTPUT_DIR / "world-bank-disputed.geojson"
    with output.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({"type": "FeatureCollection", "features": features}, output_file, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    print(f"Wrote {len(features)} World Bank disputed areas to {output}")


def main():
    source = load_json(SOURCE)
    labels = load_json(ROOT / "data/raw/wikidata/labels-zh.json")["entities"]
    dates_path = ROOT / "data/raw/wikidata/polity-dates.json"
    polity_dates = load_json(dates_path)["entities"] if dates_path.exists() else {}
    wikipedia_path = ROOT / "data/raw/wikipedia/polity-infoboxes.json"
    wikipedia = load_json(wikipedia_path)["entities"] if wikipedia_path.exists() else {}
    polity_dates = merge_wikipedia_dates(polity_dates, wikipedia)
    overrides = load_json(ROOT / "prototype/config/name-overrides.json")
    qid_overrides = load_qid_overrides()
    features = [
        prepare_feature(feature, index, labels, overrides, polity_dates, qid_overrides)
        for index, feature in enumerate(source["features"])
    ]
    mexico_1912 = next(
        feature for feature in features
        if feature["properties"]["Name"] == "Mexico" and feature["properties"]["FromYear"] == 1912
    )
    mexico_carry = json.loads(json.dumps(mexico_1912))
    mexico_carry["id"] = len(features)
    mexico_carry["properties"].update({
        "id": len(features),
        "FromYear": 1913,
        "ToYear": 1919,
        "GeometryStatus": "carry-forward",
        "ReviewStatus": "approved-case",
    })
    features.append(mexico_carry)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            output_file,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    shutil.copyfile(LICENSE, OUTPUT_DIR / "CLIO-PATRIA-LICENSE.md")
    print(f"Wrote {len(features)} features to {OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MiB)")
    prepare_base_data()
    prepare_modern_data(polity_dates)
    prepare_world_bank_disputed()
    prepare_polity_attributes()


if __name__ == "__main__":
    main()
