import os
import time
import datetime
import sqlite3
import requests
import asyncio

# --- Environment Variables (Set in Railway Dashboard) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY", "")

SYMBOL = "BTCUSDT"
DB_FILE = "trades_history.db"

# --- Virtual Account & Strategy Parameters ---
virtual_equity = 100.0   # Starting Virtual Balance ($100)
margin_per_trade = 0.10   # 10% Margin per side ($10)
leverage = 100            # 100x Leverage
tp_roi = 1.00             # Target ROI: +100%
sl_roi = 0.50             # Stop Loss: -50%

# 100x Leverage logic
price_tp_pct = tp_roi / leverage  # 0.01 (1.0% price move)
price_sl_pct = sl_roi / leverage  # 0.005 (0.5% price move)

active_positions = None 
trade_start_time = None

# --- Tracking Counters ---
bot_start_time = time.time()
last_status_time = 0
last_hourly_check = time.time()
current_hour_count = 0

trades_today = 0
trades_yesterday = 0
pnl_today = 0.0
pnl_yesterday = 0.0
total_lifetime_trades = 0

last_telegram_update_id = 0

# --- SQLite Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            date_str TEXT,
            long_status TEXT,
            long_pnl REAL,
            short_status TEXT,
            short_pnl REAL,
            net_pnl REAL
        )
    ''')
    conn.commit()
    conn.close()

def log_trade_to_db(long_status, long_pnl, short_status, short_pnl, net_pnl):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        INSERT INTO trades (timestamp, date_str, long_status, long_pnl, short_status, short_pnl, net_pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (now_str, date_str, long_status, long_pnl, short_status, short_pnl, net_pnl))
    conn.commit()
    conn.close()

def query_db_by_date(target_date):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*), SUM(net_pnl) FROM trades WHERE date_str = ?
    ''', (target_date,))
    row = cursor.fetchone()
    conn.close()
    count = row[0] if row[0] else 0
    pnl = row[1] if row[1] else 0.0
    return count, pnl

def send_telegram_msg(message):
    """Telegram Notification Dispatcher"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Log] Telegram Token or Chat ID missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            print(f"[Telegram API Error] Status Code: {res.status_code}, Response: {res.text}")
    except Exception as e:
        print(f"[Telegram Exception] {e}")

def check_telegram_commands():
    """Check incoming user messages on Telegram for date stats"""
    global last_telegram_update_id
    if not TELEGRAM_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_telegram_update_id + 1}&timeout=1"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            for update in data.get("result", []):
                last_telegram_update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "").strip()
                
                if text.startswith("/stats"):
                    parts = text.split(" ")
                    if len(parts) > 1:
                        req_date = parts[1]
                        cnt, net_p = query_db_by_date(req_date)
                        send_telegram_msg(
                            f"📅 *[DATE STATS REPORT: {req_date}]*\n\n"
                            f"• Total Sessions Executed: `{cnt}`\n"
                            f"• Total Net PnL: `${net_p:+.2f}`"
                        )
                    else:
                        send_telegram_msg(
                            f"📊 *[CURRENT OVERALL STATS]*\n\n"
                            f"• Today's Trades: `{trades_today}` (`${pnl_today:+.2f}`)\n"
                            f"• Yesterday's Trades: `{trades_yesterday}` (`${pnl_yesterday:+.2f}`)\n"
                            f"• Lifetime Trades: `{total_lifetime_trades}`\n"
                            f"• Current Equity: `${virtual_equity:.2f}`\n\n"
                            f"💡 *Tip:* Kisi specific tareekh ki detail dekhne ke liye command bhein:\n`/stats YYYY-MM-DD` (e.g. `/stats 2026-08-02`)"
                        )
    except Exception as e:
        print(f"[Telegram Listener Error] {e}")

def fetch_mexc_btc_price():
    """Fetch live market price from MEXC API"""
    url = f"https://api.mexc.com/api/v3/ticker/price?symbol={SYMBOL}"
    headers = {"Content-Type": "application/json"}
    if MEXC_API_KEY:
        headers["X-MEXC-APIKEY"] = MEXC_API_KEY
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return float(res.json()['price'])
        return None
    except Exception as e:
        print(f"[MEXC Exception] {e}")
        return None

def open_simultaneous_trades(current_price):
    global active_positions, virtual_equity, last_status_time, trade_start_time

    margin_per_side = virtual_equity * margin_per_trade
    position_size = margin_per_side * leverage

    long_tp = current_price * (1 + price_tp_pct)
    long_sl = current_price * (1 - price_sl_pct)

    short_tp = current_price * (1 - price_tp_pct)
    short_sl = current_price * (1 + price_sl_pct)

    active_positions = {
        "long": {
            "entry": current_price,
            "margin": margin_per_side,
            "tp": long_tp,
            "sl": long_sl,
            "status": "OPEN",
            "pnl": 0.0
        },
        "short": {
            "entry": current_price,
            "margin": margin_per_side,
            "tp": short_tp,
            "sl": short_sl,
            "status": "OPEN",
            "pnl": 0.0
        }
    }

    trade_start_time = time.time()
    last_status_time = time.time()

    send_telegram_msg(
        f"⚡ *[PROCESS: NEW 100X DUAL TRADES EXECUTED]*\n\n"
        f"📍 *Execution Entry Price:* `${current_price:.2f}`\n"
        f"🚀 *Leverage:* `100x` | *Total Equity:* `${virtual_equity:.2f}`\n"
        f"💵 *Margin Used:* `${margin_per_side:.2f}` per side\n\n"
        f"🟢 *LONG SETUP (BUY):*\n"
        f"• Entry: `${current_price:.2f}` | Initial PnL: `$0.00` (`0.00% ROI`)\n"
        f"• TP: `${long_tp:.2f}` (+100% ROI) | SL: `${long_sl:.2f}` (-50% ROI)\n\n"
        f"🔴 *SHORT SETUP (SELL):*\n"
        f"• Entry: `${current_price:.2f}` | Initial PnL: `$0.00` (`0.00% ROI`)\n"
        f"• TP: `${short_tp:.2f}` (+100% ROI) | SL: `${short_sl:.2f}` (-50% ROI)\n\n"
        f"⏱️ *Duration Tracker:* Active (`0 mins` elapsed)"
    )

def send_minute_update(current_price):
    if not active_positions:
        return

    elapsed_minutes = int((time.time() - trade_start_time) // 60)
    long_pos = active_positions["long"]
    short_pos = active_positions["short"]

    if long_pos["status"] == "OPEN":
        long_diff = (current_price - long_pos["entry"]) / long_pos["entry"]
        long_roi = long_diff * leverage * 100
        long_pnl = long_pos["margin"] * (long_roi / 100)
        long_str = f"🟢 *LONG:* `${long_pnl:+.2f}` (`{long_roi:+.2f}% ROI`)\n  • Entry: `${long_pos['entry']:.2f}` | TP: `${long_pos['tp']:.2f}`"
    else:
        long_str = f"🟢 *LONG:* Closed (`{long_pos['status']}` | `${long_pos['pnl']:+.2f}`)"

    if short_pos["status"] == "OPEN":
        short_diff = (short_pos["entry"] - current_price) / short_pos["entry"]
        short_roi = short_diff * leverage * 100
        short_pnl = short_pos["margin"] * (short_roi / 100)
        short_str = f"🔴 *SHORT:* `${short_pnl:+.2f}` (`{short_roi:+.2f}% ROI`)\n  • Entry: `${short_pos['entry']:.2f}` | TP: `${short_pos['tp']:.2f}`"
    else:
        short_str = f"🔴 *SHORT:* Closed (`{short_pos['status']}` | `${short_pos['pnl']:+.2f}`)"

    send_telegram_msg(
        f"⏱️ *[1-MINUTE TRADES UPDATE]*\n\n"
        f"📍 *BTC Price:* `${current_price:.2f}`\n"
        f"⏳ *Trade Duration:* `{elapsed_minutes} mins` running\n\n"
        f"{long_str}\n\n"
        f"{short_str}\n\n"
        f"💼 *Virtual Equity:* `${virtual_equity:.2f}`"
    )

def process_hourly_and_daily_checks():
    global last_hourly_check, current_hour_count
    global trades_today, trades_yesterday, pnl_today, pnl_yesterday

    now = time.time()
    # Har 1 ghante (3600 seconds) baad update
    if now - last_hourly_check >= 3600:
        current_hour_count += 1
        last_hourly_check = now

        active_status = "1 Active Session Running" if active_positions else "No Active Session"

        send_telegram_msg(
            f"⏰ *[HOURLY REPORT: Hour {current_hour_count}/24]*\n\n"
            f"• Trades Completed in Hour {current_hour_count}: `{trades_today}`\n"
            f"• Current Status: *{active_status}*\n"
            f"• Today's Net PnL So Far: `${pnl_today:+.2f}`"
        )

        # 24 Hours Complete Cycle Check
        if current_hour_count >= 24:
            send_telegram_msg(
                f"📅 *[24-HOUR CYCLE COMPLETE SUMMARY]* 🏆\n\n"
                f"☀️ *TODAY'S TOTAL TRADES:* `{trades_today}`\n"
                f"💵 *Today's Net Profit/Loss:* `${pnl_today:+.2f}`\n\n"
                f"🌙 *YESTERDAY'S TOTAL TRADES:* `{trades_yesterday}` (`${pnl_yesterday:+.2f}`)\n"
                f"📊 *COMBINED 2-DAY TOTAL TRADES:* `{trades_today + trades_yesterday}`\n"
                f"💼 *Total Account Equity:* `${virtual_equity:.2f}`\n\n"
                f"🔄 *Resetting hourly counter for the new 24-hour cycle...*"
            )

            # Roll over today stats to yesterday
            trades_yesterday = trades_today
            pnl_yesterday = pnl_today
            trades_today = 0
            pnl_today = 0.0
            current_hour_count = 0

def monitor_positions(current_price):
    global active_positions, virtual_equity, last_status_time
    global trades_today, pnl_today, total_lifetime_trades

    if not active_positions:
        return

    long_pos = active_positions["long"]
    short_pos = active_positions["short"]

    # 1. LONG Checks
    if long_pos["status"] == "OPEN":
        if current_price >= long_pos["tp"]:
            long_pos["status"] = "TP_HIT"
            long_pos["pnl"] = long_pos["margin"] * tp_roi
            send_telegram_msg(
                f"🎯 *[PROCESS: LONG TP HIT]* 🎉\n\n"
                f"📈 Position: *LONG (100x)*\n"
                f"• Entry: `${long_pos['entry']:.2f}` | Exit: `${current_price:.2f}`\n"
                f"• Profit Made: `+${long_pos['pnl']:.2f}` (+100.00% ROI)"
            )
        elif current_price <= long_pos["sl"]:
            long_pos["status"] = "SL_HIT"
            long_pos["pnl"] = -(long_pos["margin"] * sl_roi)
            send_telegram_msg(
                f"🛑 *[PROCESS: LONG SL HIT]* ❌\n\n"
                f"📈 Position: *LONG (100x)*\n"
                f"• Entry: `${long_pos['entry']:.2f}` | Exit: `${current_price:.2f}`\n"
                f"• Loss Incurred: `-${abs(long_pos['pnl']):.2f}` (-50.00% ROI)"
            )

    # 2. SHORT Checks
    if short_pos["status"] == "OPEN":
        if current_price <= short_pos["tp"]:
            short_pos["status"] = "TP_HIT"
            short_pos["pnl"] = short_pos["margin"] * tp_roi
            send_telegram_msg(
                f"🎯 *[PROCESS: SHORT TP HIT]* 🎉\n\n"
                f"📉 Position: *SHORT (100x)*\n"
                f"• Entry: `${short_pos['entry']:.2f}` | Exit: `${current_price:.2f}`\n"
                f"• Profit Made: `+${short_pos['pnl']:.2f}` (+100.00% ROI)"
            )
        elif current_price >= short_pos["sl"]:
            short_pos["status"] = "SL_HIT"
            short_pos["pnl"] = -(short_pos["margin"] * sl_roi)
            send_telegram_msg(
                f"🛑 *[PROCESS: SHORT SL HIT]* ❌\n\n"
                f"📉 Position: *SHORT (100x)*\n"
                f"• Entry: `${short_pos['entry']:.2f}` | Exit: `${current_price:.2f}`\n"
                f"• Loss Incurred: `-${abs(short_pos['pnl']):.2f}` (-50.00% ROI)"
            )

    # 3. Minute Timer Trigger
    if time.time() - last_status_time >= 60 and (long_pos["status"] == "OPEN" or short_pos["status"] == "OPEN"):
        send_minute_update(current_price)
        last_status_time = time.time()

    # 4. Session Wrap-Up & Database Persistence
    if long_pos["status"] != "OPEN" and short_pos["status"] != "OPEN":
        net_pnl = long_pos["pnl"] + short_pos["pnl"]
        virtual_equity += net_pnl

        trades_today += 1
        total_lifetime_trades += 1
        pnl_today += net_pnl

        # Log entry to local SQLite database
        log_trade_to_db(long_pos["status"], long_pos["pnl"], short_pos["status"], short_pos["pnl"], net_pnl)

        summary_emoji = "🟢" if net_pnl > 0 else "🔴"

        send_telegram_msg(
            f"📊 *[PROCESS: SESSION COMPLETE]* {summary_emoji}\n\n"
            f"• LONG (100x): `{long_pos['status']}` (`${long_pos['pnl']:+.2f}`)\n"
            f"• SHORT (100x): `{short_pos['status']}` (`${short_pos['pnl']:+.2f}`)\n\n"
            f"💵 *Net Session PnL:* `${net_pnl:+.2f}`\n"
            f"💼 *Updated Virtual Equity:* `${virtual_equity:.2f}`\n"
            f"🔢 *Today's Total Completed Sessions:* `{trades_today}`\n\n"
            f"⚡ *[INSTANT RE-ENTRY]:* Opening next 100x dual trades..."
        )

        active_positions = None

async def main_loop():
    init_db()
    auth_status = "Authenticated API" if MEXC_API_KEY else "Public API"
    
    send_telegram_msg(
        f"🤖 *[PROCESS: BOT INITIALIZED & ONLINE]*\n\n"
        f"• Exchange Feed: *MEXC Realtime ({auth_status})*\n"
        f"• Pair: *{SYMBOL}* | Leverage: *100x*\n"
        f"• Features: *Live Minute Updates, Elapsed Time, Hourly & 24h Cycles, Database History Logging*\n\n"
        f"📱 *Telegram Command Enabled:* Send `/stats` or `/stats YYYY-MM-DD` anytime to query history."
    )

    while True:
        try:
            # Check for incoming Telegram user commands (/stats)
            check_telegram_commands()

            # Check Hourly/Daily timing logic
            process_hourly_and_daily_checks()

            current_price = fetch_mexc_btc_price()
            if current_price:
                if active_positions is None:
                    open_simultaneous_trades(current_price)
                else:
                    monitor_positions(current_price)

            await asyncio.sleep(2)

        except Exception as e:
            print(f"[Main Loop Exception] {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main_loop())
