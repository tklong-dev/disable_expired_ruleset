#!/usr/bin/env python3
import sys
import os
import io
import time
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding='utf-8')
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding='utf-8')

from disable_expired_ruleset.adapter.utils.env_loader import load_env
from disable_expired_ruleset.adapter.utils.console import (
    color, header, info, warn, error, success,
    CYAN, BOLD, RED, YELLOW, GREEN,
)
from disable_expired_ruleset.adapter.api.cloudflare_api import disable_rule, enable_rule
from disable_expired_ruleset.adapter.telegram.bot import send_message, poll_for_message
from disable_expired_ruleset.modules.action_log import list_logs, load_log, save_disable_log
from disable_expired_ruleset.modules.pending_disable import load_pending, clear_pending

load_env(Path(__file__).parent.parent / "variables" / ".env")
API_TOKEN  = os.environ.get("CF_API_TOKEN", "")
TG_TIMEOUT = int(os.environ.get("TG_TIMEOUT", "120"))


# ---------------------------------------------------------------------------
# Disable flow (triggered khi user gui yes/no sau khi main.py scan xong)
# ---------------------------------------------------------------------------

def _prompt_pending_disable(entries: list):
    """Gui lai message nhac nho neu listener restart khi co pending."""
    lines = [
        f"• *{e['name']}*\n  Domain : {e['zone_name']}\n  Het han: {e['expiry']}"
        for e in entries
    ]
    send_message(
        f"⚠️ *Con pending DISABLE {len(entries)} rule(s)*\n\n"
        + "\n\n".join(lines)
        + "\n\nGui `yes` de thuc thi, `no` de huy"
    )


def handle_disable_confirm(sender: str | None, entries: list):
    name = sender or "?"
    send_message(f"✅ *{name}* xac nhan. Dang disable *{len(entries)}* rule(s)...")
    info(f"{name} xac nhan disable. Dang xu ly...")

    results      = []
    result_lines = []
    for e in entries:
        info(f"Dang disable: {e['name'][:55]}...")
        try:
            disable_rule(e, API_TOKEN)
            results.append((e, e["expiry"], None))
            result_lines.append(f"✅ *{e['name']}*\n   Domain: {e['zone_name']}")
            success("Da disable.")
        except RuntimeError as ex:
            results.append((e, e["expiry"], str(ex)))
            result_lines.append(f"❌ *{e['name']}*\n   Loi: {ex}")
            error(f"That bai: {ex}")

    ok_count  = sum(1 for _, _, err in results if err is None)
    err_count = sum(1 for _, _, err in results if err is not None)

    summary = "📋 *KET QUA DISABLE*\n\n" + "\n\n".join(result_lines)
    summary += f"\n\n✅ {ok_count} disabled"
    if err_count:
        summary += f"  ❌ {err_count} loi"
    send_message(summary)

    log_path = save_disable_log(results)
    if log_path:
        info(f"Da luu log rollback: {color(log_path.name, CYAN)}")

    clear_pending()


def handle_disable_cancel(sender: str | None):
    name = sender or "?"
    send_message(f"🚫 *{name}* da huy. Khong disable rule nao.")
    info(f"{name} huy disable.")
    clear_pending()


# ---------------------------------------------------------------------------
# Rollback flow (triggered khi user gui /rollback)
# ---------------------------------------------------------------------------

def handle_rollback(trigger_sender: str | None):
    logs = list_logs()
    if not logs:
        send_message("⚠️ Khong tim thay log nao. Hay chay `main.py` va disable rules truoc.")
        warn("Khong co log.")
        return

    log_data = [load_log(p) for p in logs]

    session_lines = []
    for i, (log_path, data) in enumerate(zip(logs, log_data), start=1):
        count = len(data.get("disabled", []))
        ts    = log_path.stem.replace("disable_", "")
        session_lines.append(f"`[{i}]`  `{ts}`  —  {count} rules")

    ts_name  = trigger_sender or "?"
    session_msg = (
        f"📋 Chon session rollback ({ts_name}):\n\n"
        + "\n".join(session_lines)
        + f"\n\nGui so thu tu de chon (timeout: {TG_TIMEOUT}s)"
    )
    resp = send_message(session_msg)
    if not resp.get("ok"):
        warn(f"Khong gui duoc session list: {resp.get('description')}")
        return
    info("Da gui danh sach session. Dang cho chon...")

    # Loop cho den khi nhan duoc so hop le, bo qua lenh /... va input sai
    idx      = None
    deadline = time.time() + TG_TIMEOUT
    while idx is None:
        remaining = int(deadline - time.time())
        if remaining <= 0:
            send_message("Timeout — Da huy rollback.")
            warn("Timeout chon session.")
            return
        choice_text, _ = poll_for_message(timeout_sec=remaining)
        if choice_text == "timeout":
            send_message("Timeout — Da huy rollback.")
            warn("Timeout chon session.")
            return
        c = choice_text.strip()
        if c.startswith("/"):
            send_message(f"Vui long gui SO THU TU session (1 den {len(logs)}), khong phai lenh.\nVi du: 1")
            continue
        if c.isdigit() and (1 <= int(c) <= len(logs)):
            idx = int(c) - 1
        else:
            send_message(f"Khong hop le. Vui long gui so tu 1 den {len(logs)}.")

    data    = log_data[idx]
    entries = data.get("disabled", [])
    ts      = logs[idx].stem.replace("disable_", "")

    if not entries:
        send_message("⚠️ Session nay khong co rule nao.")
        return

    rule_lines = [
        f"• {e['name']}\n  Domain : {e['zone_name']}\n  Het han: {e['expiry']}"
        for e in entries
    ]
    resp = send_message(
        f"Session: {ts}\n\n"
        + "\n\n".join(rule_lines)
        + f"\n\nXac nhan RE-ENABLE {len(entries)} rule(s)?\n"
        f"Gui yes de thuc thi, no de huy (timeout: {TG_TIMEOUT}s)"
    )
    if not resp.get("ok"):
        warn(f"Khong gui duoc confirm message: {resp.get('description')}")
        return
    info("Da gui danh sach rules. Dang cho xac nhan...")

    response, sender = poll_for_message(timeout_sec=TG_TIMEOUT)
    if response == "timeout":
        send_message("⏰ Timeout — Da huy rollback.")
        warn("Timeout xac nhan rollback.")
        return

    if response.strip().lower() != "yes":
        send_message(f"{sender} da huy rollback.")
        info(f"{sender} chon no.")
        return

    send_message(f"{sender} xac nhan. Dang re-enable {len(entries)} rule(s)...")
    info(f"{sender} xac nhan. Dang re-enable...")

    ok_count     = 0
    err_count    = 0
    result_lines = []
    for e in entries:
        info(f"Dang re-enable: {e['name'][:55]}...")
        try:
            enable_rule(e, API_TOKEN)
            result_lines.append(f"OK: {e['name']}\n   Domain: {e['zone_name']}")
            ok_count += 1
            success("Da re-enable.")
        except RuntimeError as ex:
            result_lines.append(f"FAIL: {e['name']}\n   Loi: {ex}")
            err_count += 1
            error(f"That bai: {ex}")

    result_msg = "KET QUA ROLLBACK\n\n" + "\n\n".join(result_lines)
    result_msg += f"\n\n{ok_count} re-enabled"
    if err_count:
        result_msg += f"  {err_count} loi"
    send_message(result_msg)

    print(f"  {color('Tong:', BOLD)} {color(ok_count, GREEN, BOLD)} re-enabled"
          + (f"  {color(err_count, RED, BOLD)} loi" if err_count else "") + "\n")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    header("TELEGRAM LISTENER")
    info("Dang lang nghe lenh tu group Telegram...")

    # Kiem tra neu co pending disable tu lan chay main.py truoc
    pending = load_pending()
    if pending:
        warn(f"Tim thay pending disable: {len(pending)} rule(s). Nhac nho group...")
        _prompt_pending_disable(pending)

    send_message(
        "🤖 *Listener da san sang.*\n"
        "• `/rollback` — rollback rules da disable\n"
        "• `yes` / `no` — xac nhan pending disable (neu co)"
    )

    while True:
        text, sender = poll_for_message(timeout_sec=0)  # cho mai mai
        # Strip @BotUsername — Telegram groups append it to commands
        cmd = text.strip().lower().split()[0].split("@")[0] if text.strip() else ""
        info(f"[{sender}] '{text[:50]}'  →  cmd='{cmd}'")

        pending = load_pending()

        if cmd == "/rollback":
            info(f"Nhan /rollback tu {sender}.")
            handle_rollback(trigger_sender=sender)
            info("Hoan thanh rollback. Tiep tuc lang nghe...")

        elif pending and cmd == "yes":
            info(f"Nhan xac nhan 'yes' tu {sender} cho pending disable.")
            handle_disable_confirm(sender=sender, entries=pending)
            info("Hoan thanh disable. Tiep tuc lang nghe...")

        elif pending and cmd == "no":
            info(f"Nhan 'no' tu {sender}. Huy pending disable.")
            handle_disable_cancel(sender=sender)

        else:
            # Bo qua tin nhan khong lien quan
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{color('  Da dung listener.', YELLOW)}\n")
        sys.exit(0)
