import os
import time
import requests

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8967600024:AAG49_G08n_3D0sV7qt9SjTOHPD4bmmzZNI")
CHAT_ID   = os.environ.get("TG_CHAT_ID",   "-5020538280")

_SESSION = requests.Session()
_offset: int | None = None  # shared across all poll calls


def _init_offset():
    """Drain old updates once at startup, set shared offset."""
    global _offset
    if _offset is not None:
        return
    data    = _SESSION.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", json={"timeout": 0}).json()
    updates = data.get("result", [])
    if not updates:
        _offset = 0
        return
    latest  = updates[-1]["update_id"]
    _SESSION.post(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", json={"offset": latest + 1, "timeout": 0})
    _offset = latest + 1
    print(f"  [BOT] init offset={_offset}, CHAT_ID={CHAT_ID}")


def send_message(text: str) -> dict:
    resp = _SESSION.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=10,
    ).json()
    if not resp.get("ok"):
        print(f"  [TG ERROR] send_message that bai: {resp}")
    return resp


def _next_update(chunk: int) -> list:
    """Fetch next batch of updates, update shared offset. Returns list of updates."""
    global _offset
    try:
        data = _SESSION.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            json={"offset": _offset, "timeout": chunk},
            timeout=chunk + 5,
        ).json()
    except Exception as e:
        print(f"  [BOT] _next_update exception: {e}")
        time.sleep(2)
        return []

    updates = data.get("result", [])
    for upd in updates:
        _offset = upd["update_id"] + 1
    return updates


def poll_for_message(timeout_sec: int = 0) -> tuple[str, str | None]:
    """
    Cho den khi co bat ky tin nhan nao tu CHAT_ID.
    timeout_sec=0 → cho mai mai.
    Returns: (text, sender)  hoac  ("timeout", None)
    """
    _init_offset()
    deadline = (time.time() + timeout_sec) if timeout_sec > 0 else None

    while True:
        if deadline is not None:
            remaining = int(deadline - time.time())
            if remaining <= 0:
                return "timeout", None
            chunk = min(remaining, 30)
        else:
            chunk = 30

        for upd in _next_update(chunk):
            msg = upd.get("message")
            if not msg:
                continue
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text    = (msg.get("text") or "").strip()
            sender  = msg.get("from", {}).get("first_name", "?")
            print(f"  [BOT] recv chat={chat_id} sender={sender} text={text!r}")
            if chat_id == str(CHAT_ID) and text:
                return text, sender


def poll_for_response(timeout_sec: int = 120, valid_responses: tuple = ("yes", "no")) -> tuple[str, str | None]:
    """
    Cho den khi nhan duoc mot trong valid_responses tu CHAT_ID.
    Returns: (response_text, sender)  hoac  ("timeout", None)
    """
    _init_offset()
    deadline = time.time() + timeout_sec

    while True:
        remaining = int(deadline - time.time())
        if remaining <= 0:
            return "timeout", None

        for upd in _next_update(min(remaining, 30)):
            msg = upd.get("message")
            if not msg:
                continue
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text    = (msg.get("text") or "").strip().lower()
            sender  = msg.get("from", {}).get("first_name", "?")
            print(f"  [BOT] recv chat={chat_id} sender={sender} text={text!r}")
            if chat_id == str(CHAT_ID) and text in valid_responses:
                return text, sender
