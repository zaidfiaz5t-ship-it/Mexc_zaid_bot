import os
import time
import requests
import asyncio

# --- Configuration & Environment Variables ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs")
TELEGRAM_CHAT_ID = os.getenv("8013586305", "YOUR_CHAT_ID_HERE")
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "mx0vglAfCE8tKXscOi")

SYMBOL = "BTCUSDT"

# --- Virtual Account & Strategy Parameters ---
virtual_equity = 100.0  # Initial Virtual Balance
margin_per_trade = 0.10  # 10% Margin per side (Total 20% in play)
tp_roi = 1.00            # +100% ROI Target
sl_roi = 0.50            # -50% SL Cutoff

# Holds both Active Long & Short positions
active_positions = None 

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Telegram Token Missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Notification Error: {e}")

def fetch_mexc_btc_price():
    """MEXC REST API se real-time BTC price fetch karta hai"""
    url = f"https://api.mexc.com/api/v3/ticker/price?symbol={SYMBOL}"
    headers = {}
    if MEXC_API_KEY:
        headers["X-MEXC-APIKEY"] = MEXC_API_KEY
    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        return float(data['price'])
    except Exception as e:
        print(f"MEXC Fetch Error: {e}")
        return None

def open_simultaneous_trades(current_price):
    global active_positions, virtual_equity

    margin_per_side = virtual_equity * margin_per_trade

    # Long Position Parameters (+100% TP / -50% SL)
    long_tp = current_price * (1 + (tp_roi * margin_per_trade))
    long_sl = current_price * (1 - (sl_roi * margin_per_trade))

    # Short Position Parameters (+100% TP / -50% SL)
    short_tp = current_price * (1 - (tp_roi * margin_per_trade))
    short_sl = current_price * (1 + (sl_roi * margin_per_trade))

    active_positions = {
        "long": {
            "entry": current_price,
            "margin": margin_per_side,
            "tp": long_tp,
            "sl": long_sl,
            "status": "OPEN",  # OPEN, TP_HIT, SL_HIT
            "pnl": 0.0
        },
        "short": {
            "entry": current_price,
            "margin": margin_per_side,
            "tp": short_tp,
            "sl": short_sl,
            "status": "OPEN",  # OPEN, TP_HIT, SL_HIT
            "pnl": 0.0
        }
    }

    send_telegram_msg(
        f"⚔️ *Simultaneous Long & Short Positions Opened!*\n\n"
        f"📍 *Entry Price:* `${current_price:.2f}`\n"
        f"💰 *Margin Per Side (10%):* `${margin_per_side:.2f}` (Total: `${margin_per_side*2:.2f}`)\n\n"
        f"📈 *LONG:* TP `${long_tp:.2f}` | SL `${long_sl:.2f}`\n"
        f"📉 *SHORT:* TP `${short_tp:.2f}` | SL `${short_sl:.2f}`\n\n"
        f"💼 *Total Account Equity:* `${virtual_equity:.2f}`"
    )

def monitor_positions(current_price):
    global active_positions, virtual_equity

    if not active_positions:
        return

    long_pos = active_positions["long"]
    short_pos = active_positions["short"]

    # --- 1. Check LONG Trade ---
    if long_pos["status"] == "OPEN":
        if current_price >= long_pos["tp"]:
            long_pos["status"] = "TP_HIT"
            long_pos["pnl"] = long_pos["margin"] * tp_roi
            send_telegram_msg(f"🎯 *LONG Position TP Hit!* Profit: `+${long_pos['pnl']:.2f}`")
        elif current_price <= long_pos["sl"]:
            long_pos["status"] = "SL_HIT"
            long_pos["pnl"] = -(long_pos["margin"] * sl_roi)
            send_telegram_msg(f"🛑 *LONG Position SL Hit!* Loss: `-${abs(long_pos['pnl']):.2f}`")

    # --- 2. Check SHORT Trade ---
    if short_pos["status"] == "OPEN":
        if current_price <= short_pos["tp"]:
            short_pos["status"] = "TP_HIT"
            short_pos["pnl"] = short_pos["margin"] * tp_roi
            send_telegram_msg(f"🎯 *SHORT Position TP Hit!* Profit: `+${short_pos['pnl']:.2f}`")
        elif current_price >= short_pos["sl"]:
            short_pos["status"] = "SL_HIT"
            short_pos["pnl"] = -(short_pos["margin"] * sl_roi)
            send_telegram_msg(f"🛑 *SHORT Position SL Hit!* Loss: `-${abs(short_pos['pnl']):.2f}`")

    # --- 3. Close Session When BOTH Trades Hit TP or SL ---
    if long_pos["status"] != "OPEN" and short_pos["status"] != "OPEN":
        net_session_pnl = long_pos["pnl"] + short_pos["pnl"]
        virtual_equity += net_session_pnl

        result_emoji = "🎉" if net_session_pnl > 0 else "❌"
        send_telegram_msg(
            f"🔄 *Both Positions Closed! Session Finished* {result_emoji}\n\n"
            f"📈 LONG Result: `{long_pos['status']}` (`${long_pos['pnl']:.2f}`)\n"
            f"📉 SHORT Result: `{short_pos['status']}` (`${short_pos['pnl']:.2f}`)\n"
            f"📊 *Net Session PnL:* `${net_session_pnl:+.2f}`\n"
            f"💼 *Updated Virtual Equity:* `${virtual_equity:.2f}`\n\n"
            f"⏳ *Opening Next Dual Trade Set Immediately...*"
        )

        # Clear position state so new pair can open on next tick
        active_positions = None

async def main_loop():
    send_telegram_msg(
        f"🤖 *Dual-Hedge Grid Bot Live on Railway!*\n"
        f"Initial Virtual Equity: `$100.00`\n"
        f"Mode: *Simultaneous Buy & Sell*\n"
        f"Scanning Real-Time Price..."
    )

    while True:
        try:
            current_price = fetch_mexc_btc_price()

            if current_price:
                if active_positions is None:
                    open_simultaneous_trades(current_price)
                else:
                    monitor_positions(current_price)

            await asyncio.sleep(2)  # Fast 2-second price tracking

        except Exception as e:
            print(f"Loop Exception: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main_loop())

 
 