import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = ROOT / "prototype/config/entity-qid-overrides.json"


def load_qid_overrides():
    if not OVERRIDES.exists():
        return {}
    with OVERRIDES.open(encoding="utf-8") as override_file:
        return json.load(override_file)


def correct_qid(properties, overrides):
    source = properties.get("Wikidata", "")
    title = properties.get("Wikipedia", "")
    return overrides.get(f"{source}|{title}", {}).get("target", source)
