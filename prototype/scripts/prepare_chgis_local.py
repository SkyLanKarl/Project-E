import json
import shutil
from pathlib import Path

import shapefile

from prepare_data import label_point

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/chgis/v6/extracted/v6_time_pref_pgn_utf_wgs84.shp"
OUTPUT_DIR = ROOT / "prototype/local"
OUTPUT = OUTPUT_DIR / "chgis-prefectures.geojson"


def main():
    reader = shapefile.Reader(str(SOURCE), encoding="utf-8")
    features = []
    for index, shape_record in enumerate(reader.iterShapeRecords()):
        record = shape_record.record.as_dict()
        shape = shape_record.shape
        if shape.shapeTypeName != "POLYGON" or not shape.points:
            continue
        geometry = shape.__geo_interface__
        center_x = record.get("X_COOR") or 0
        center_y = record.get("Y_COOR") or 0
        center = [center_x, center_y] if center_x and center_y else label_point(geometry)
        features.append({
            "type": "Feature",
            "id": index,
            "properties": {
                "id": index,
                "Name": record.get("NAME_PY") or "",
                "NameZh": record.get("NAME_CH") or record.get("NAME_PY") or "",
                "NameTraditional": record.get("NAME_FT") or "",
                "NameReview": "chgis",
                "FromYear": int(record["BEG_YR"]),
                "ToYear": int(record["END_YR"]),
                "FromRule": record.get("BEG_RULE") or "",
                "ToRule": record.get("END_RULE") or "",
                "Area": 0,
                "Wikipedia": "",
                "Wikidata": "",
                "MemberOf": "",
                "Components": "",
                "Dynasty": record.get("DYN_CH") or "",
                "Type": record.get("TYPE_CH") or "",
                "GeoSource": record.get("GEO_SRC") or "",
                "Compiler": record.get("COMPILER") or "",
                "Checker": record.get("CHECKER") or "",
                "role": "chgis-prefecture",
                "GeometryStatus": "source",
                "SourceFromYear": int(record["BEG_YR"]),
                "SourceToYear": int(record["END_YR"]),
                "ReviewStatus": "source",
                "Source": "CHGIS",
                "LabelPoint": center,
                "LabelPriority": 1,
                "LabelMinZoom": 4,
                "color": 1,
            },
            "geometry": geometry,
        })
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump({"type": "FeatureCollection", "features": features}, output_file, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    shutil.copyfile(ROOT / "data/raw/chgis/v6/CHGIS_V6_EULA.txt", OUTPUT_DIR / "CHGIS-EULA.txt")
    shutil.copyfile(ROOT / "data/raw/chgis/v6/source.json", OUTPUT_DIR / "CHGIS-SOURCE.json")
    print(f"Wrote {len(features)} local-only CHGIS prefectures to {OUTPUT}")


if __name__ == "__main__":
    main()
