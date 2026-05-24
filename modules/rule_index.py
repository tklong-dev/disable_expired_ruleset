from disable_expired_ruleset.adapter.api.cloudflare_api import fetch_rules
from disable_expired_ruleset.modules.rule_types import RULE_TYPES
from disable_expired_ruleset.modules.rule_utils import resolve_rule_name, is_rule_enabled


def build_rule_index(zones: list, token: str, rules_cache: dict = None) -> list:
    index = []

    for zone in zones:
        zone_id   = zone["id"]
        zone_name = zone["name"]

        for rule_type in RULE_TYPES:
            if rules_cache is not None:
                rules = rules_cache.get((zone_id, rule_type["label"]), [{"_empty": True}])
            else:
                rules = fetch_rules(zone_id, token, rule_type)

            real_rules = [r for r in rules if not r.get("_error")]

            for rule in real_rules:
                rule_id = rule.get("id", "")
                if not rule_id:
                    continue

                index.append({
                    "name":        resolve_rule_name(rule, rule_type),
                    "rule_id":     rule_id,
                    "zone_name":   zone_name,
                    "enabled":     is_rule_enabled(rule),
                    "toggle_info": {
                        "zone_id":    zone_id,
                        "ruleset_id": rule.get("_ruleset_id"),
                    },
                })

    return index
