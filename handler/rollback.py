#!/usr/bin/env python3
import sys
import os
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from disable_expired_ruleset.adapter.utils.env_loader import load_env
from disable_expired_ruleset.adapter.utils.console import (
    color, header, info, warn, error, success,
    CYAN, WHITE, BOLD, DIM, MAGENTA, RED, YELLOW, GREEN,
)
from disable_expired_ruleset.adapter.api.cloudflare_api import enable_rule
from disable_expired_ruleset.modules.action_log import list_logs, load_log

load_env(Path(__file__).parent.parent / "variables" / ".env")
API_TOKEN = os.environ.get("CF_API_TOKEN", "")


def main():
    header("CLOUDFLARE RULES ROLLBACK")

    if not API_TOKEN:
        error("Chua co API Token. Vui long khai bao CF_API_TOKEN trong variables/.env")
        sys.exit(1)

    logs = list_logs()
    if not logs:
        warn("Khong tim thay log nao. Hay chay main.py va disable rules truoc.")
        sys.exit(0)

    log_data = [load_log(p) for p in logs]

    info(f"Tim thay {color(len(logs), CYAN, BOLD)} session(s) co the rollback:")
    print()
    for i, (log_path, data) in enumerate(zip(logs, log_data), start=1):
        count = len(data.get("disabled", []))
        ts    = log_path.stem.replace("disable_", "")
        print(f"    {color(f'[{i}]', CYAN, BOLD)}  {color(ts, WHITE, BOLD)}  "
              f"{color(f'({count} rules)', DIM)}")

    print()
    choice = input(color("  Chon session (so thu tu, Enter = session moi nhat): ", YELLOW)).strip()

    if choice == "":
        idx = 0
    elif choice.isdigit() and 1 <= int(choice) <= len(logs):
        idx = int(choice) - 1
    else:
        error("Lua chon khong hop le.")
        sys.exit(1)

    data    = log_data[idx]
    entries = data.get("disabled", [])

    if not entries:
        warn("Session nay khong co rule nao.")
        sys.exit(0)

    print(f"\n  {color('Session :', BOLD)} {color(data['timestamp'], CYAN)}")
    print(f"  {color('Rules se duoc RE-ENABLE:', BOLD)}\n")
    for e in entries:
        print(f"    {color('●', CYAN)}  {color(e['name'], WHITE, BOLD)}")
        print(f"         Domain : {color(e['zone_name'], MAGENTA)}")
        print(f"         Het han: {color(e['expiry'], RED)}")
        print()

    confirm = input(color("  Xac nhan RE-ENABLE tat ca rules tren? (yes/no): ", YELLOW)).strip().lower()
    if confirm not in ("yes", "y"):
        info("Bo qua, khong re-enable.")
        return

    print()
    ok_count  = 0
    err_count = 0
    for e in entries:
        info(f"Dang re-enable: {e['name'][:55]}...")
        try:
            enable_rule(e, API_TOKEN)
            success("Da re-enable.")
            ok_count += 1
        except RuntimeError as ex:
            error(f"That bai: {ex}")
            err_count += 1

    header("TONG HOP KET QUA")
    print(f"  {color('Tong:', BOLD)} {color(ok_count, GREEN, BOLD)} re-enabled"
          + (f"  {color(err_count, RED, BOLD)} loi" if err_count else "") + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{color('  Da huy boi nguoi dung.', YELLOW)}\n")
        sys.exit(0)
