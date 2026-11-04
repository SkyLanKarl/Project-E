import hashlib
import json
import shutil
from pathlib import Path

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


def prepare_feature(feature, index, labels, overrides):
    properties = feature["properties"]
    name = properties["Name"]
    qid = properties.get("Wikidata") or ""
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


def prepare_modern_data():
    source = load_json(ROOT / "data/raw/natural-earth/geojson/ne_50m_admin_0_countries.geojson")
    features = []
    for index, feature in enumerate(source["features"]):
        properties = feature["properties"]
        name = properties.get("NAME_EN") or properties["NAME"]
        sovereignty = properties.get("SOVEREIGNT") or name
        is_member = properties.get("TYPE") not in {"Sovereign country", "Country"} and sovereignty != name
        features.append({
            "type": "Feature",
            "id": index,
            "properties": {
                "id": index,
                "Name": name,
                "NameZh": properties.get("NAME_ZH") or name,
                "NameReview": "natural-earth",
                "FromYear": 2024,
                "ToYear": 2024,
                "Area": 0,
                "Wikipedia": name,
                "Wikidata": properties.get("WIKIDATAID") or "",
                "MemberOf": f"({sovereignty})" if is_member else "",
                "Components": "",
                "role": "member" if is_member else "polity",
                "GeometryStatus": "reference",
                "SourceFromYear": 2024,
                "SourceToYear": 2024,
                "ReviewStatus": "pending",
                "Type": properties.get("TYPE") or "",
                "Sovereignty": sovereignty,
                "LabelPoint": label_point(feature["geometry"]),
                "LabelPriority": properties.get("POP_EST") or 0,
                "color": color_index(name),
            },
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": round_coordinates(feature["geometry"]["coordinates"]),
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


def main():
    source = load_json(SOURCE)
    labels = load_json(ROOT / "data/raw/wikidata/labels-zh.json")["entities"]
    overrides = load_json(ROOT / "prototype/config/name-overrides.json")
    features = [
        prepare_feature(feature, index, labels, overrides)
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
    prepare_modern_data()


if __name__ == "__main__":
    main()
