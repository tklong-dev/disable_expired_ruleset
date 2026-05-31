import json
from pathlib import Path

PENDING_FILE = Path(__file__).resolve().parent.parent / "variables" / "pending_disable.json"


def save_pending(expired: list):
    data = [
        {
            "name":        entry["name"],
            "rule_id":     entry["rule_id"],
            "zone_name":   entry["zone_name"],
            "toggle_info": entry["toggle_info"],
            "expiry":      str(expiry),
        }
        for entry, expiry in expired
    ]
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_pending() -> list | None:
    if not PENDING_FILE.exists():
        return None
    with open(PENDING_FILE, encoding="utf-8") as f:
        return json.load(f)


def clear_pending():
    PENDING_FILE.unlink(missing_ok=True)
