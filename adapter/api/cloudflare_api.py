import json
import time
import urllib.request
import urllib.error

from disable_expired_ruleset.adapter.utils.console import warn

BASE_URL   = "https://api.cloudflare.com/client/v4"
MAX_RETRY  = 3
RETRY_BASE = 2  # seconds, exponential: 2, 4, 8


def _parse_http_error(e: urllib.error.HTTPError) -> str:
    body = e.read().decode()
    try:
        msgs = [err.get("message", "") for err in json.loads(body).get("errors", [])]
        return f"HTTP {e.code}: {'; '.join(msgs) or body}"
    except json.JSONDecodeError:
        return f"HTTP {e.code}: {body}"


def _retry_request(req) -> dict:
    for attempt in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRY - 1:
                wait = RETRY_BASE ** (attempt + 1)
                warn(f"Rate limited (429), thu lai sau {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(_parse_http_error(e))
        except urllib.error.URLError as e:
            raise RuntimeError(f"Khong ket noi duoc toi Cloudflare API: {e.reason}")


def cf_request(path: str, token: str) -> dict:
    req = urllib.request.Request(BASE_URL + path, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    return _retry_request(req)


def cf_patch(path: str, token: str, payload) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    return _retry_request(req)


def get_all_zones(token: str) -> list:
    zones    = []
    page     = 1
    per_page = 50
    while True:
        data        = cf_request(f"/zones?per_page={per_page}&page={page}", token)
        result      = data.get("result", [])
        result_info = data.get("result_info", {})
        zones.extend(result)
        total_pages = result_info.get("total_pages", 1)
        if page >= total_pages or not result:
            break
        page += 1
    return zones


def fetch_rules(zone_id: str, token: str, rule_type: dict) -> list:
    endpoint = f"/zones/{zone_id}{rule_type['endpoint']}"
    try:
        data = cf_request(endpoint, token)
    except RuntimeError as e:
        if "404" in str(e):
            return []
        return [{"_error": str(e)}]

    result = data.get("result", [])

    if rule_type.get("phase_endpoint"):
        if isinstance(result, dict):
            ruleset_id = result.get("id")
            inner      = result.get("rules", [])
            for r in inner:
                r["_ruleset_id"] = ruleset_id
            return inner
        return []

    return result


def _set_rule_enabled(entry: dict, token: str, enabled: bool):
    ti         = entry["toggle_info"]
    rule_id    = entry["rule_id"]
    zone_id    = ti["zone_id"]
    ruleset_id = ti.get("ruleset_id")

    if not ruleset_id:
        raise RuntimeError("Khong co ruleset_id. Chay lai de refresh.")

    all_rules = cf_request(f"/zones/{zone_id}/rulesets/{ruleset_id}", token).get("result", {}).get("rules", [])
    target    = next((r for r in all_rules if r.get("id") == rule_id), None)

    if target is None:
        raise RuntimeError(f"Khong tim thay rule_id={rule_id} trong ruleset_id={ruleset_id}")

    _READ_ONLY = {"version", "last_updated", "ref"}
    payload = {k: v for k, v in target.items() if k not in _READ_ONLY and k != "_ruleset_id"}
    payload["enabled"] = enabled

    resp = cf_patch(f"/zones/{zone_id}/rulesets/{ruleset_id}/rules/{rule_id}", token, payload)

    errs = resp.get("errors", [])
    if errs:
        raise RuntimeError("; ".join(e.get("message", str(e)) for e in errs))

    if not resp.get("success", True):
        raise RuntimeError("CF tra ve success=false.")


def disable_rule(entry: dict, token: str):
    _set_rule_enabled(entry, token, False)


def enable_rule(entry: dict, token: str):
    _set_rule_enabled(entry, token, True)
