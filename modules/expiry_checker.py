import re
from datetime import date


def parse_expiry(name: str):
    m = re.search(r'_expire-(\d{4}-\d{2}-\d{2})', name, re.IGNORECASE)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def find_expired(index: list, today: date) -> list:
    return [
        (entry, expiry)
        for entry in index
        if entry["enabled"]
        and (expiry := parse_expiry(entry["name"])) is not None
        and expiry < today
    ]
