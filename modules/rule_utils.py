def resolve_rule_name(rule: dict, rule_type: dict) -> str:
    name_key = rule_type.get("name_key")
    if name_key and rule.get(name_key):
        return rule[name_key]
    return rule.get("description") or rule.get("expression", "")[:60] or "(no name)"


def is_rule_enabled(rule: dict) -> bool:
    if "paused" in rule:
        return not rule["paused"]
    if "enabled" in rule:
        return rule["enabled"]
    if rule.get("status") == "active":
        return True
    if rule.get("status") == "disabled":
        return False
    return True
