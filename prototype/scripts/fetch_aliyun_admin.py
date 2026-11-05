import json
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data/raw/aliyun-datav"
API = "https://geo.datav.aliyun.com/areas_v3/bound/{name}.json"


def load(path):
    with path.open(encoding="utf-8") as source_file:
        data = json.load(source_file)
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError(f"Invalid FeatureCollection: {path}")
    return data


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "ProjectE-HistoricalResearchPrototype/0.1 (local research use)"
    requested = set()
    level_counts = Counter()

    def download(name):
        requested.add(name)
        output = OUTPUT_DIR / f"{name}.json"
        if output.exists():
            return load(output)
        for attempt in range(5):
            try:
                response = session.get(API.format(name=name), timeout=60)
                if response.status_code == 404:
                    print(f"No subordinate boundary file for {name}")
                    return {"type": "FeatureCollection", "features": []}
                response.raise_for_status()
                data = response.json()
                if data.get("type") != "FeatureCollection":
                    raise ValueError(f"Unexpected response for {name}")
                temporary = output.with_suffix(".json.tmp")
                temporary.write_text(
                    json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                temporary.replace(output)
                break
            except (requests.RequestException, ValueError):
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
        time.sleep(0.1)
        return load(output)

    def record(data):
        for feature in data["features"]:
            level = (feature.get("properties") or {}).get("level")
            if level:
                level_counts[level] += 1

    country = download("100000")
    record(country)
    provinces = download("100000_full")
    record(provinces)
    province_codes = [
        str(feature["properties"]["adcode"])
        for feature in provinces["features"]
        if feature["properties"].get("level") == "province"
    ]
    for code in province_codes:
        province = download(code)
        record(province)
        cities = download(f"{code}_full")
        record(cities)
        for feature in cities["features"]:
            properties = feature.get("properties") or {}
            if properties.get("level") == "city" and properties.get("childrenNum", 0) > 0:
                city_code = str(properties["adcode"])
                districts = download(f"{city_code}_full")
                record(districts)
        print(f"Completed province {code}; cached requests {len(requested)}")
        requested.update({code, f"{code}_full"})

    files = list(OUTPUT_DIR.glob("*.json"))
    print(f"Completed {len(files)} files ({sum(p.stat().st_size for p in files) / 1024 / 1024:.1f} MiB)")
    print("Feature levels:", dict(sorted(level_counts.items())))


if __name__ == "__main__":
    main()
