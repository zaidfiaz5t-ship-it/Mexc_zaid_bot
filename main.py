import os
import time
import requests
import asyncio

# --- Environment Variables (Set in Railway Dashboard) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY", "")

SYMBOL = "BTCUSDT"

# --- Virtual Account & Strategy Parameters ---
virtual_equity = 100.0   # Starting Virtual Balance ($100)
margin_per_trade = 0.10   # 10% Margin per side ($10)
leverage = 100            # 100x Leverage
tp_roi = 1.00             # Target ROI: +100%
sl_roi = 0.50             # Stop Loss: -50%

# Price movement logic for 100x Leverage
price_tp_pct = tp_roi / leverage  # 0.01 (1.0% price move)
price_sl_pct = sl_roi / leverage  # 0.005 (0.5% price move)

active_positions = None 
last_status_time = 0      # Timer to track 1-minute updates

def send_telegram_msg(message):
    """Telegram Notification Dispatcher"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Log] Telegram Token or Chat ID missing in Railway Variables!")
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

def fetch_mexc_btc_price():
    """Fetch authenticated live market price from MEXC API"""
    url = f"https://api.mexc.com/api/v3/ticker/price?symbol={SYMBOL}"
    headers = {"Content-Type": "application/json"}
    
    if MEXC_API_KEY:
        headers["X-MEXC-APIKEY"] = MEXC_API_KEY

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return float(data['price'])
        else:
            print(f"[MEXC API Error] Code: {res.status_code}, Message: {res.text}")
            return None
    except Exception as e:
        print(f"[MEXC Connection Exception] {e}")
        return None

def open_simultaneous_trades(current_price):
    global active_positions, virtual_equity, last_status_time

    margin_per_side = virtual_equity * margin_per_trade
    position_size = margin_per_side * leverage  # $10 * 100 = $1,000 position size per side

    # 100x Leverage Target Price Calculations
    long_tp = current_price * (1 + price_tp_pct)
    long_sl = current_price * (1 - price_sl_pct)

    short_tp = current_price * (1 - price_tp_pct)
    short_sl = current_price * (1 + price_sl_pct)

    active_positions = {
        "long": {
            "entry": current_price,
            "margin": margin_per_side,
            "position_size": position_size,
            "tp": long_tp,
            "sl": long_sl,
            "status": "OPEN",
            "pnl": 0.0
        },
        "short": {
            "entry": current_price,
            "margin": margin_per_side,
            "position_size": position_size,
            "tp": short_tp,
            "sl": short_sl,
            "status": "OPEN",
            "pnl": 0.0
        }
    }

    last_status_time = time.time()  # Reset 1-min timer

    # Initial Trade Execution Alert with PnL & ROI
    send_telegram_msg(
        f"⚡ *[PROCESS: NEW 100X DUAL TRADES EXECUTED]*\n\n"
        f"📍 *Execution Entry Price:* `${current_price:.2f}`\n"
        f"🚀 *Leverage:* `100x` | *Total Equity:* `${virtual_equity:.2f}`\n"
        f"💵 *Margin Used:* `${margin_per_side:.2f}` per side\n"
        f"📊 *Position Volume:* `${position_size:.2f}` per side ($1,000 Vol)\n\n"
        f"🟢 *LONG SETUP (BUY):*\n"
        f"• Entry: `${current_price:.2f}`\n"
        f"• Initial PnL: `$0.00` (`0.00% ROI`)\n"
        f"• Target TP (+100% ROI / +1.0% Move): `${long_tp:.2f}`\n"
        f"• Stop Loss (-50% ROI / -0.5% Move): `${long_sl:.2f}`\n\n"
        f"🔴 *SHORT SETUP (SELL):*\n"
        f"• Entry: `${current_price:.2f}`\n"
        f"• Initial PnL: `$0.00` (`0.00% ROI`)\n"
        f"• Target TP (+100% ROI / -1.0% Move): `${short_tp:.2f}`\n"
        f"• Stop Loss (-50% ROI / +0.5% Move): `${short_sl:.2f}`\n\n"
        f"📲 *Status:* Live 1-minute updates activated..."
    )

def send_minute_update(current_price):
    """Sends 1-Minute Live Performance Alert for Active Trades"""
    if not active_positions:
        return

    long_pos = active_positions["long"]
    short_pos = active_positions["short"]

    # Calculate Current Live PnL & ROI for LONG
    if long_pos["status"] == "OPEN":
        long_price_diff_pct = (current_price - long_pos["entry"]) / long_pos["entry"]
        long_roi = long_price_diff_pct * leverage * 100
        long_pnl = long_pos["margin"] * (long_roi / 100)
        long_str = f"🟢 *LONG:* `${long_pnl:+.2f}` (`{long_roi:+.2f}% ROI`)\n  • Entry: `${long_pos['entry']:.2f}` | TP: `${long_pos['tp']:.2f}`"
    else:
        long_str = f"🟢 *LONG:* Closed (`{long_pos['status']}` | `${long_pos['pnl']:+.2f}`)"

    # Calculate Current Live PnL & ROI for SHORT
    if short_pos["status"] == "OPEN":
        short_price_diff_pct = (short_pos["entry"] - current_price) / short_pos["entry"]
        short_roi = short_price_diff_pct * leverage * 100
        short_pnl = short_pos["margin"] * (short_roi / 100)
        short_str = f"🔴 *SHORT:* `${short_pnl:+.2f}` (`{short_roi:+.2f}% ROI`)\n  • Entry: `${short_pos['entry']:.2f}` | TP: `${short_pos['tp']:.2f}`"
    else:
        short_str = f"🔴 *SHORT:* Closed (`{short_pos['status']}` | `${short_pos['pnl']:+.2f}`)"

    send_telegram_msg(
        f"⏱️ *[1-MINUTE TRADES UPDATE]*\n\n"
        f"📍 *Current BTC Price:* `${current_price:.2f}`\n\n"
        f"{long_str}\n\n"
        f"{short_str}\n\n"
        f"💼 *Virtual Equity:* `${virtual_equity:.2f}`"
    )

def monitor_positions(current_price):
    global active_positions, virtual_equity, last_status_time

    if not active_positions:
        return

    long_pos = active_positions["long"]
    short_pos = active_positions["short"]

    # 1. LONG Position Checks
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

    # 2. SHORT Position Checks
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

    # 3. Check for 1-Minute Live Update Timer
    if time.time() - last_status_time >= 60 and (long_pos["status"] == "OPEN" or short_pos["status"] == "OPEN"):
        send_minute_update(current_price)
        last_status_time = time.time()

    # 4. Session Wrap-Up & Instant Re-execution
    if long_pos["status"] != "OPEN" and short_pos["status"] != "OPEN":
        net_pnl = long_pos["pnl"] + short_pos["pnl"]
        virtual_equity += net_pnl

        summary_emoji = "🟢" if net_pnl > 0 else "🔴"

        send_telegram_msg(
            f"📊 *[PROCESS: SESSION COMPLETE]* {summary_emoji}\n\n"
            f"• LONG (100x): `{long_pos['status']}` (`${long_pos['pnl']:+.2f}`)\n"
            f"• SHORT (100x): `{short_pos['status']}` (`${short_pos['pnl']:+.2f}`)\n\n"
            f"💵 *Net Session PnL:* `${net_pnl:+.2f}`\n"
            f"💼 *Updated Virtual Equity:* `${virtual_equity:.2f}`\n\n"
            f"⚡ *[INSTANT RE-ENTRY]:* Opening next 100x dual trades..."
        )

        active_positions = None  # Instantly opens new dual trades on the very next loop

async def main_loop():
    auth_status = "Authenticated API" if MEXC_API_KEY else "Public API"
    
    send_telegram_msg(
        f"🤖 *[PROCESS: BOT INITIALIZED & ONLINE]*\n\n"
        f"• Feed: *MEXC Realtime ({auth_status})*\n"
        f"• Target Pair: *{SYMBOL}*\n"
        f"• Virtual Capital: `$100.00`\n"
        f"• Leverage: *100x*\n"
        f"• Updates: *Every 60 Seconds Live PnL ($ & ROI)*\n"
        f"• Execution: *Auto Re-Entry on Session Close*\n\n"
        f"🚀 *Scanning live market prices now...*"
    )

    while True:
        try:
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
