import json
import re
import time
from collections import Counter, deque
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data/raw/geojson-cn"
API = "https://geojson.cn/api/china/1.6.3/{code}.json"


def read_feature_collection(path):
    with path.open(encoding="utf-8") as source_file:
        data = json.load(source_file)
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError(f"Invalid FeatureCollection: {path}")
    return data


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "ProjectE-HistoricalResearchPrototype/0.1 (local research use)"
    pending = deque(["china"])
    queued = {"china"}
    downloaded = set()
    level_counts = Counter()

    while pending:
        code = pending.popleft()
        if not re.fullmatch(r"[A-Za-z0-9_/-]+", code) or ".." in code or code.startswith("/"):
            raise ValueError(f"Unexpected administrative code: {code}")
        output = OUTPUT_DIR / f"{code}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.exists():
            for attempt in range(5):
                try:
                    response = session.get(API.format(code=code), timeout=60)
                    if response.status_code == 403:
                        raise PermissionError(
                            f"{code}: GeoJSON.cn reports that city/county data authorization is required"
                        )
                    response.raise_for_status()
                    data = response.json()
                    if data.get("type") != "FeatureCollection":
                        raise ValueError(f"Unexpected response for {code}")
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
            time.sleep(0.15)
        data = read_feature_collection(output)
        downloaded.add(code)
        for feature in data["features"]:
            properties = feature.get("properties") or {}
            level = properties.get("level")
            level_counts[level] += 1
            child = properties.get("filename") or properties.get("code")
            if child and level is not None and level < 3 and child not in queued:
                queued.add(child)
                pending.append(str(child))
        print(f"{code}: {len(data['features'])} features; total files {len(downloaded)}; queued {len(pending)}")

    total_size = sum((OUTPUT_DIR / f"{code}.json").stat().st_size for code in downloaded)
    print(f"Completed {len(downloaded)} files ({total_size / 1024 / 1024:.1f} MiB)")
    print("Feature levels:", dict(sorted(level_counts.items(), key=lambda item: str(item[0]))))


if __name__ == "__main__":
    main()
