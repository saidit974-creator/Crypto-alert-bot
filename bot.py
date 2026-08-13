import json, os, time, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALERTS_FILE = ROOT / "alerts.json"
STATE_FILE = ROOT / "state.json"
OFFSET_FILE = ROOT / "telegram_offset.txt"

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_CHAT_ID = str(os.environ["ALLOWED_CHAT_ID"]).strip()

TG = f"https://api.telegram.org/bot{BOT_TOKEN}"
BINANCE = "https://api.binance.com/api/v3/ticker/price?symbol="

def http_json(url, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("User-Agent", "crypto-alert-bot/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def tg_send(text):
    payload = urllib.parse.urlencode({
        "chat_id": ALLOWED_CHAT_ID,
        "text": text,
        "disable_web_page_preview": "true"
    }).encode()
    return http_json(TG + "/sendMessage", payload)

def tg_updates(offset=None):
    params = {"timeout": 1}
    if offset is not None:
        params["offset"] = offset
    url = TG + "/getUpdates?" + urllib.parse.urlencode(params)
    return http_json(url)

def get_price(symbol):
    data = http_json(BINANCE + urllib.parse.quote(symbol))
    return float(data["price"])

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

def load_offset():
    try:
        return int(OFFSET_FILE.read_text().strip())
    except Exception:
        return None

def save_offset(value):
    OFFSET_FILE.write_text(str(value))

def normalize_symbol(s):
    s = s.upper().replace("/", "").replace("-", "")
    if not s.endswith("USDT"):
        s += "USDT"
    return s

def fmt_price(p):
    if p >= 1000: return f"{p:,.2f}"
    if p >= 1: return f"{p:,.4f}".rstrip("0").rstrip(".")
    if p >= 0.01: return f"{p:.6f}".rstrip("0").rstrip(".")
    return f"{p:.10f}".rstrip("0").rstrip(".")

def help_text():
    return (
        "📡 Crypto Alert Bot\n\n"
        "Commands:\n"
        "/add BTC above 120000\n"
        "/add SUI below 3.5\n"
        "/add ETH above 5000\n"
        "/list\n"
        "/del 3\n"
        "/clear\n"
        "/help\n\n"
        "The bot checks Binance Spot prices every ~5 minutes.\n"
        "Each alert fires once, then becomes inactive.\n"
        "To reuse it, add it again."
    )

def process_command(text, alerts):
    parts = text.strip().split()
    if not parts:
        return "Use /help"

    cmd = parts[0].lower()

    if cmd == "/help" or cmd == "/start":
        return help_text()

    if cmd == "/list":
        active = [a for a in alerts if a.get("active", True)]
        if not active:
            return "📭 No active alerts."
        lines = ["🔔 Active alerts:"]
        for a in active:
            lines.append(f"#{a['id']}  {a['symbol']} {a['condition']} {fmt_price(a['target'])}")
        return "\n".join(lines)

    if cmd == "/clear":
        for a in alerts:
            a["active"] = False
        return "🗑 All alerts disabled."

    if cmd == "/del":
        if len(parts) != 2 or not parts[1].isdigit():
            return "Usage: /del 3"
        n = int(parts[1])
        found = False
        for a in alerts:
            if a["id"] == n and a.get("active", True):
                a["active"] = False
                found = True
                break
        return "✅ Alert deleted." if found else "❌ Alert not found."

    if cmd == "/add":
        if len(parts) != 4:
            return "Usage: /add BTC above 120000"
        symbol = normalize_symbol(parts[1])
        condition = parts[2].lower()
        if condition not in ("above", "below"):
            return "Condition must be 'above' or 'below'."
        try:
            target = float(parts[3])
            if target <= 0:
                raise ValueError
        except ValueError:
            return "Target must be a positive number."

        # Validate symbol and get current price now.
        try:
            price = get_price(symbol)
        except Exception:
            return f"❌ Binance could not find/return {symbol}."
        next_id = max([a["id"] for a in alerts] + [0]) + 1
        alerts.append({
            "id": next_id,
            "symbol": symbol,
            "condition": condition,
            "target": target,
            "active": True
        })
        return (
            f"✅ Added #{next_id}\n"
            f"{symbol} {condition} {fmt_price(target)}\n"
            f"Current: {fmt_price(price)}"
        )

    return "Unknown command. Use /help"

def main():
    alerts = load_json(ALERTS_FILE, [])
    state = load_json(STATE_FILE, {})
    offset = load_offset()

    # Process Telegram commands.
    updates = tg_updates(offset)
    if updates.get("ok"):
        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message", {})
            chat = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "")
            if chat == ALLOWED_CHAT_ID and text.startswith("/"):
                reply = process_command(text, alerts)
                save_json(ALERTS_FILE, alerts)
                tg_send(reply)
        if offset is not None:
            save_offset(offset)

    # Check active alerts.
    changed = False
    for a in alerts:
        if not a.get("active", True):
            continue
        try:
            price = get_price(a["symbol"])
        except Exception:
            continue

        hit = (a["condition"] == "above" and price >= a["target"]) or \
              (a["condition"] == "below" and price <= a["target"])

        if hit:
            tg_send(
                f"🚨 ALERT #{a['id']}\n"
                f"{a['symbol']} is {a['condition']} {fmt_price(a['target'])}\n"
                f"Current price: {fmt_price(price)}"
            )
            a["active"] = False
            changed = True

    if changed:
        save_json(ALERTS_FILE, alerts)

if __name__ == "__main__":
    main()
