#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# When run directly, add Code_Repository to sys.path so the package is found
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

from disable_expired_ruleset.adapter.utils.env_loader import load_env
from disable_expired_ruleset.adapter.utils.console import (
    color, header, section, info, warn, error, success,
    CYAN, WHITE, BOLD, DIM, MAGENTA, RED, YELLOW, GREEN,
)
from disable_expired_ruleset.adapter.api.cloudflare_api import (
    get_all_zones, fetch_rules, disable_rule,
)
from disable_expired_ruleset.modules.rule_types import RULE_TYPES
from disable_expired_ruleset.modules.rule_index import build_rule_index
from disable_expired_ruleset.modules.expiry_checker import find_expired
from disable_expired_ruleset.modules.display import (
    display_rule, domain_header, print_domain_summary, print_grand_summary,
)
from disable_expired_ruleset.modules.action_log import save_disable_log
from disable_expired_ruleset.modules.rule_utils import is_rule_enabled

load_env(Path(__file__).parent.parent / "variables" / ".env")
API_TOKEN = os.environ.get("CF_API_TOKEN", "")


def main():
    header("CLOUDFLARE DOMAIN RULES VIEWER")

    if not API_TOKEN:
        error("Chua co API Token. Vui long khai bao CF_API_TOKEN trong variables/.env")
        sys.exit(1)

    # 1. Lay toan bo domains
    info("Dang lay danh sach domains...")
    try:
        zones = get_all_zones(API_TOKEN)
    except RuntimeError as e:
        msg = str(e)
        if "401" in msg or "403" in msg or "10000" in msg:
            error(f"Token khong hop le hoac het han: {msg}")
        else:
            error(f"Khong lay duoc zones: {msg}")
        sys.exit(1)

    if not zones:
        warn("Khong tim thay domain nao trong tai khoan.")
        sys.exit(0)

    success(f"Tim thay {color(len(zones), CYAN, BOLD)} domain(s):")
    for z in zones:
        print(f"    {color('*', CYAN)}  {color(z['name'], WHITE, BOLD)}  {color(z['id'], DIM)}")

    # 2. Fetch tat ca rules song song (concurrent)
    info("Dang tai rules cho tat ca domains...")
    rules_cache = {}
    tasks = [(zone["id"], rt) for zone in zones for rt in RULE_TYPES]
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        future_map = {
            executor.submit(fetch_rules, zone_id, API_TOKEN, rt): (zone_id, rt["label"])
            for zone_id, rt in tasks
        }
        for future in as_completed(future_map):
            zone_id, rt_label = future_map[future]
            rules_cache[(zone_id, rt_label)] = future.result()

    # 3. Hien thi rules tren tung domain
    all_totals = []

    for i, zone in enumerate(zones, start=1):
        zone_id   = zone["id"]
        zone_name = zone["name"]

        domain_header(zone_name, zone_id, i, len(zones))
        totals = {}

        for rule_type in RULE_TYPES:
            section(rule_type["label"])
            rules      = rules_cache.get((zone_id, rule_type["label"]), [])
            real_rules = [r for r in rules if not r.get("_error")]
            e_count    = 0
            d_count    = 0

            if not rules:
                info("Khong co rule nao.")
            else:
                for idx, rule in enumerate(rules, start=1):
                    display_rule(idx, rule, rule_type)

            for rule in real_rules:
                if is_rule_enabled(rule):
                    e_count += 1
                else:
                    d_count += 1

            totals[rule_type["label"]] = {"enabled": e_count, "disabled": d_count}

        print_domain_summary(totals, zone_name)
        all_totals.append((zone_name, totals))

    # 4. Grand summary
    print_grand_summary(all_totals)

    # 5. Kiem tra va xu ly rules het han
    today      = date.today()
    rule_index = build_rule_index(zones, API_TOKEN, rules_cache)
    expired    = find_expired(rule_index, today)

    if not expired:
        return

    header("RULES DA HET HAN")
    for entry, expiry in expired:
        days_ago = (today - expiry).days
        print(f"  {color('●', RED, BOLD)}  {color(entry['name'], WHITE, BOLD)}")
        print(f"       Domain  : {color(entry['zone_name'], MAGENTA)}")
        print(f"       Het han : {color(str(expiry), RED, BOLD)}  "
              f"{color('(' + str(days_ago) + ' ngay truoc)', DIM)}")
        print()

    print(color(f"  Tong cong {len(expired)} rule(s) het han.", YELLOW, BOLD))
    print()
    confirm = input(
        color("  Xac nhan DISABLE tat ca rules het han tren? (yes/no): ", YELLOW)
    ).strip().lower()

    if confirm not in ("yes", "y"):
        info("Bo qua, khong disable.")
        return

    print()
    results = []
    for entry, expiry in expired:
        info(f"Dang disable: {entry['name'][:55]}...")
        try:
            disable_rule(entry, API_TOKEN)
            entry["enabled"] = False
            results.append((entry, expiry, None))
            success("Da disable.")
        except RuntimeError as e:
            results.append((entry, expiry, str(e)))
            error(f"That bai: {e}")

    header("TONG HOP KET QUA")
    ok_count  = 0
    err_count = 0
    for entry, expiry, err in results:
        if err is None:
            print(f"  {color('OK', GREEN, BOLD)}  {color(entry['name'], WHITE, BOLD)}")
            print(f"       Domain  : {color(entry['zone_name'], MAGENTA)}")
            print(f"       Het han : {color(str(expiry), RED)}")
            ok_count += 1
        else:
            print(f"  {color('XX', RED, BOLD)}  {color(entry['name'], WHITE, BOLD)}")
            print(f"       Loi     : {color(err, RED)}")
            err_count += 1
        print()

    print(f"  {color('Tong:', BOLD)} {color(ok_count, GREEN, BOLD)} disabled"
          + (f"  {color(err_count, RED, BOLD)} loi" if err_count else "") + "\n")

    log_path = save_disable_log(results)
    if log_path:
        info(f"Da luu log rollback: {color(log_path.name, CYAN)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{color('  Da huy boi nguoi dung.', YELLOW)}\n")
        sys.exit(0)
