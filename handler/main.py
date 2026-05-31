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
    get_all_zones, fetch_rules,
)
from disable_expired_ruleset.adapter.telegram.bot import send_message
from disable_expired_ruleset.modules.rule_types import RULE_TYPES
from disable_expired_ruleset.modules.rule_index import build_rule_index
from disable_expired_ruleset.modules.expiry_checker import find_expired
from disable_expired_ruleset.modules.display import (
    display_rule, domain_header, print_domain_summary, print_grand_summary,
)
from disable_expired_ruleset.modules.rule_utils import is_rule_enabled
from disable_expired_ruleset.modules.pending_disable import save_pending

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
        info("Khong co rule nao het han.")
        send_message(f"✅ Khong co rule nao het han hom nay ({today}).")
        return

    header("RULES DA HET HAN")
    tg_lines = []
    for entry, expiry in expired:
        days_ago = (today - expiry).days
        print(f"  {color('●', RED, BOLD)}  {color(entry['name'], WHITE, BOLD)}")
        print(f"       Domain  : {color(entry['zone_name'], MAGENTA)}")
        print(f"       Het han : {color(str(expiry), RED, BOLD)}  "
              f"{color('(' + str(days_ago) + ' ngay truoc)', DIM)}")
        print()
        tg_lines.append(
            f"• *{entry['name']}*\n"
            f"  Domain : {entry['zone_name']}\n"
            f"  Het han: {expiry} ({days_ago} ngay truoc)"
        )

    print(color(f"  Tong cong {len(expired)} rule(s) het han.", YELLOW, BOLD))
    print()

    # Luu pending va gui Telegram — listener.py se xu ly phan hoi
    save_pending(expired)
    tg_msg = (
        f"⚠️ *RULES DA HET HAN* — {len(expired)} rule(s)\n\n"
        + "\n\n".join(tg_lines)
        + f"\n\n❓ Xac nhan DISABLE {len(expired)} rule(s) tren?\n"
        f"Gui `yes` de thuc thi, `no` de huy"
    )
    info("Dang gui thong bao sang Telegram...")
    send_message(tg_msg)
    success("Da gui. listener.py se xu ly khi ban gui yes/no trong group.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{color('  Da huy boi nguoi dung.', YELLOW)}\n")
        sys.exit(0)
