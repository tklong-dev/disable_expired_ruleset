from disable_expired_ruleset.adapter.utils.console import (
    color, header, info, warn,
    WHITE, BOLD, CYAN, GREEN, RED, MAGENTA, DIM,
)
from disable_expired_ruleset.modules.rule_utils import resolve_rule_name

_RULE_TYPE_COLOR = {
    "Custom Rules (WAF)": CYAN,
}


def display_rule(idx: int, rule: dict, rule_type: dict):
    if rule.get("_error"):
        warn(f"[{idx}] Khong lay duoc: {rule['_error']}")
        return

    c    = _RULE_TYPE_COLOR.get(rule_type["label"], WHITE)
    name = resolve_rule_name(rule, rule_type)
    print(f"  {color(f'[{idx:>3}]', c, BOLD)}  {color(name, WHITE, BOLD)}")


def domain_header(name: str, zone_id: str, idx: int, total: int):
    line = "-" * 60
    print(f"\n{color(line, MAGENTA)}")
    print(f"{color('  [' + str(idx) + '/' + str(total) + '] DOMAIN: ' + name, MAGENTA, BOLD)}")
    print(f"{color('  Zone ID: ' + zone_id, DIM)}")
    print(f"{color(line, MAGENTA)}")


def print_domain_summary(totals: dict, zone_name: str):
    total_e = sum(v["enabled"]  for v in totals.values())
    total_d = sum(v["disabled"] for v in totals.values())
    total   = total_e + total_d
    if total == 0:
        return
    print(f"\n  {color('Summary ' + zone_name + ':', BOLD)}")
    for label, counts in totals.items():
        t = counts["enabled"] + counts["disabled"]
        if t == 0:
            continue
        e_bar       = color("+" * min(counts["enabled"],  20), GREEN)
        d_bar       = color("-" * min(counts["disabled"], 20), RED)
        short_label = f"{label[:32]:<32}"
        print(f"    {color(short_label, DIM)}  {color(str(t).rjust(3), WHITE, BOLD)}"
              f"  [{e_bar}{d_bar}]"
              f"  {color(str(counts['enabled']) + ' on',  GREEN)}"
              f"  {color(str(counts['disabled']) + ' off', RED)}")
    print(f"\n    {color('Total:', BOLD)} {color(total, WHITE, BOLD)} rules"
          f"  [ {color(str(total_e) + ' ENABLED',  GREEN, BOLD)}"
          f"  {color(str(total_d) + ' DISABLED', RED, BOLD)} ]\n")


def print_grand_summary(all_totals: list):
    header("TONG KET TOAN BO HE THONG")
    grand_e = 0
    grand_d = 0
    for zone_name, totals in all_totals:
        total_e = sum(v["enabled"]  for v in totals.values())
        total_d = sum(v["disabled"] for v in totals.values())
        grand_e += total_e
        grand_d += total_d
        total   = total_e + total_d
        if total == 0:
            st = color("(no rules)", DIM)
        else:
            st = (f"{color(str(total_e) + ' on',  GREEN, BOLD)}  "
                  f"{color(str(total_d) + ' off', RED, BOLD)}  "
                  f"{color('(' + str(total) + ' total)', DIM)}")
        zn = f"{zone_name:<35}"
        print(f"  {color('*', CYAN)}  {color(zn, WHITE, BOLD)}  {st}")
    print(f"\n  {color('=' * 58, CYAN)}")
    print(f"  {color('Grand Total:', BOLD)}  "
          f"{color(grand_e + grand_d, WHITE, BOLD)} rules  "
          f"[ {color(str(grand_e) + ' ENABLED',  GREEN, BOLD)}  "
          f"{color(str(grand_d) + ' DISABLED', RED, BOLD)} ]\n")
