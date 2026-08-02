import os
import time
import requests
import asyncio

# --- Configuration & Environment Variables ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs")
TELEGRAM_CHAT_ID = os.getenv("8013586305", "YOUR_CHAT_ID_HERE")
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "mx0vglAfCE8tKXscOi")

SYMBOL = "BTCUSDT"

# --- Virtual Account & Risk Parameters ---
virtual_equity = 100.0   # Starting Capital ($100)
margin_per_trade = 0.10   # 10% Margin per side (Total 20% in play)
tp_roi = 1.00             # Target ROI: +100%
sl_roi = 0.50             # Stop Loss: -50%

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
    """MEXC REST API se real-time price pull karta hai"""
    url = f"https://api.mexc.com/api/v3/ticker/price?symbol={SYMBOL}"
    headers = {}
    if MEXC_API_KEY:
        headers["X-MEXC-APIKEY"] = MEXC_API_KEY
    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        return float(data['price'])
    except Exception as e:
        print(f"MEXC Price Fetch Error: {e}")
        return None

def open_simultaneous_trades(current_price):
    global active_positions, virtual_equity

    margin_per_side = virtual_equity * margin_per_trade

    # Price Calculation based on ROI %
    long_tp = current_price * (1 + (tp_roi * margin_per_trade))
    long_sl = current_price * (1 - (sl_roi * margin_per_trade))

    short_tp = current_price * (1 - (tp_roi * margin_per_trade))
    short_sl = current_price * (1 + (sl_roi * margin_per_trade))

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

    # Complete Step-by-Step Execution Notification
    send_telegram_msg(
        f"⚡ *[PROCESS: NEW TRADES EXECUTED]*\n\n"
        f"📍 *Execution Market Price:* `${current_price:.2f}`\n"
        f"💰 *Current Equity Balance:* `${virtual_equity:.2f}`\n"
        f"💵 *Margin Used (10% Per Side):* `${margin_per_side:.2f}` (Total: `${margin_per_side*2:.2f}`)\n\n"
        f"🟢 *LONG TRADE SETUP:* \n"
        f"• Entry: `${current_price:.2f}`\n"
        f"• Target TP (+100% ROI): `${long_tp:.2f}`\n"
        f"• Stop Loss (-50% ROI): `${long_sl:.2f}`\n\n"
        f"🔴 *SHORT TRADE SETUP:* \n"
        f"• Entry: `${current_price:.2f}`\n"
        f"• Target TP (+100% ROI): `${short_tp:.2f}`\n"
        f"• Stop Loss (-50% ROI): `${short_sl:.2f}`\n\n"
        f"👀 *Status:* Live tracking active. Waiting for TP/SL levels..."
    )

def monitor_positions(current_price):
    global active_positions, virtual_equity

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
                f"📈 Position: *LONG / BUY*\n"
                f"• Entry Price: `${long_pos['entry']:.2f}`\n"
                f"• Target TP Hit Price: `${current_price:.2f}`\n"
                f"• Profit Made: `+${long_pos['pnl']:.2f}` (+100% ROI)"
            )
        elif current_price <= long_pos["sl"]:
            long_pos["status"] = "SL_HIT"
            long_pos["pnl"] = -(long_pos["margin"] * sl_roi)
            send_telegram_msg(
                f"🛑 *[PROCESS: LONG SL HIT]* ❌\n\n"
                f"📈 Position: *LONG / BUY*\n"
                f"• Entry Price: `${long_pos['entry']:.2f}`\n"
                f"• Stop Loss Hit Price: `${current_price:.2f}`\n"
                f"• Loss Incurred: `-${abs(long_pos['pnl']):.2f}` (-50% ROI)"
            )

    # 2. SHORT Position Checks
    if short_pos["status"] == "OPEN":
        if current_price <= short_pos["tp"]:
            short_pos["status"] = "TP_HIT"
            short_pos["pnl"] = short_pos["margin"] * tp_roi
            send_telegram_msg(
                f"🎯 *[PROCESS: SHORT TP HIT]* 🎉\n\n"
                f"📉 Position: *SHORT / SELL*\n"
                f"• Entry Price: `${short_pos['entry']:.2f}`\n"
                f"• Target TP Hit Price: `${current_price:.2f}`\n"
                f"• Profit Made: `+${short_pos['pnl']:.2f}` (+100% ROI)"
            )
        elif current_price >= short_pos["sl"]:
            short_pos["status"] = "SL_HIT"
            short_pos["pnl"] = -(short_pos["margin"] * sl_roi)
            send_telegram_msg(
                f"🛑 *[PROCESS: SHORT SL HIT]* ❌\n\n"
                f"📉 Position: *SHORT / SELL*\n"
                f"• Entry Price: `${short_pos['entry']:.2f}`\n"
                f"• Stop Loss Hit Price: `${current_price:.2f}`\n"
                f"• Loss Incurred: `-${abs(short_pos['pnl']):.2f}` (-50% ROI)"
            )

    # 3. Session Wrap Up (Jab dono Long & Short ke results final ho jayein)
    if long_pos["status"] != "OPEN" and short_pos["status"] != "OPEN":
        net_pnl = long_pos["pnl"] + short_pos["pnl"]
        virtual_equity += net_pnl

        summary_emoji = "🟢" if net_pnl > 0 else "🔴"

        send_telegram_msg(
            f"📊 *[PROCESS: SESSION COMPLETE]* {summary_emoji}\n\n"
            f"• LONG Status: `{long_pos['status']}` (`${long_pos['pnl']:+.2f}`)\n"
            f"• SHORT Status: `{short_pos['status']}` (`${short_pos['pnl']:+.2f}`)\n\n"
            f"💵 *Net Session PnL:* `${net_pnl:+.2f}`\n"
            f"💼 *Updated Equity Balance:* `${virtual_equity:.2f}`\n\n"
            f"🔄 *Next Step:* Triggering new dual-hedge trades..."
        )

        active_positions = None  # Free for next execution

async def main_loop():
    # BOT STARTUP NOTIFICATION
    send_telegram_msg(
        f"🤖 *[PROCESS: BOT INITIALIZED]*\n\n"
        f"• Status: *Online & Connected to MEXC Realtime Feed*\n"
        f"• Pair: *{SYMBOL}*\n"
        f"• Virtual Capital: `$100.00`\n"
        f"• Strategy: *Dual-Hedge Long & Short*\n"
        f"• Target Setup: *+100% TP / -50% SL*\n\n"
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

            await asyncio.sleep(2)  # 2-second interval scanning

        except Exception as e:
            print(f"Main Loop Exception: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main_loop())
