import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "variables" / "logs"


def save_disable_log(results: list) -> Path | None:
    successful = [(entry, expiry) for entry, expiry, err in results if err is None]
    if not successful:
        return None

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = LOG_DIR / f"disable_{timestamp}.json"

    entries = [
        {
            "name":        entry["name"],
            "rule_id":     entry["rule_id"],
            "zone_name":   entry["zone_name"],
            "toggle_info": entry["toggle_info"],
            "expiry":      str(expiry),
        }
        for entry, expiry in successful
    ]

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": timestamp, "disabled": entries}, f, ensure_ascii=False, indent=2)

    return log_path


def list_logs() -> list:
    if not LOG_DIR.exists():
        return []
    return sorted(LOG_DIR.glob("disable_*.json"), reverse=True)


def load_log(log_path: Path) -> dict:
    with open(log_path, encoding="utf-8") as f:
        return json.load(f)
