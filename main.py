import os
import asyncio
import json
import time
import requests
import pandas as pd
import numpy as np

# Railway Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8013586305")
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "mx0vglAfCE8tKXscOi")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY", "5591ea266c5141bcbfe5f37782c84ac2")

SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"

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
        print(f"Telegram Alert Error: {e}")

def fetch_mexc_klines(limit=100):
    """MEXC API se BTC/USDT 15m K-line data fetch karta hai"""
    url = f"https://api.mexc.com/api/v3/klines?symbol={SYMBOL}&interval={TIMEFRAME}&limit={limit}"
    
    headers = {}
    if MEXC_API_KEY:
        headers["X-MEXC-APIKEY"] = MEXC_API_KEY

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume'
        ])
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df
    except Exception as e:
        print(f"Error fetching MEXC data: {e}")
        return None

def analyze_candle(df):
    pivots = 10
    recent_df = df.iloc[-pivots*2:-1]
    resistance = recent_df['high'].max()
    support = recent_df['low'].min()

    next_resistance = resistance + (resistance - support)
    next_support = support - (resistance - support)

    last_candle = df.iloc[-2] # Recently closed candle
    prev_candles = df.iloc[:-1]

    close_price = last_candle['close']
    vol = last_candle['volume']

    is_breakout_up = close_price > resistance
    is_breakout_down = close_price < support

    if not is_breakout_up and not is_breakout_down:
        return

    # 1. Analyzing Alert
    send_telegram_msg("🔍 *[MEXC Scanning]* Breakout Detected on BTC/USDT 15m.\nChecking SMC Filters...")

    reasons = []

    # Filter 1: Volume Spike Check
    avg_vol = prev_candles['volume'].tail(20).mean()
    if vol <= avg_vol * 1.2:
        reasons.append(f"Low Volume Spike (Vol: {vol:.1f} vs Avg: {avg_vol:.1f})")

    # Filter 2: FVG Gap Check
    if is_breakout_up:
        c1_high = prev_candles.iloc[-3]['high']
        c3_low = last_candle['low']
        if c3_low > c1_high:
            fvg_gap = (c3_low - c1_high) / close_price
            if fvg_gap > 0.003: # 0.3% Threshold
                reasons.append("Unfilled FVG Gap Below Entry")
    elif is_breakout_down:
        c1_low = prev_candles.iloc[-3]['low']
        c3_high = last_candle['high']
        if c3_high < c1_low:
            fvg_gap = (c1_low - c3_high) / close_price
            if fvg_gap > 0.003:
                reasons.append("Unfilled FVG Gap Above Entry")

    # Send Notification Results
    if is_breakout_up:
        send_telegram_msg(f"⚡ *MEXC Breakout:* Resistance Broken @ `{resistance:.2f}`")
        if not reasons:
            send_telegram_msg(
                f"✅ *Verification Passed! All SMC Filters Clear.*\n\n"
                f"📈 *Signal: BUY / LONG*\n"
                f"📍 *Entry:* `{close_price:.2f}`\n"
                f"🛑 *SL:* `{support:.2f}`\n"
                f"🎯 *TP:* `{next_resistance:.2f}`"
            )
        else:
            send_telegram_msg(f"❌ *Verification Failed! Trade Skipped.*\n*Reason:* {', '.join(reasons)}")

    elif is_breakout_down:
        send_telegram_msg(f"⚡ *MEXC Breakout:* Support Broken @ `{support:.2f}`")
        if not reasons:
            send_telegram_msg(
                f"✅ *Verification Passed! All SMC Filters Clear.*\n\n"
                f"📉 *Signal: SELL / SHORT*\n"
                f"📍 *Entry:* `{close_price:.2f}`\n"
                f"🛑 *SL:* `{resistance:.2f}`\n"
                f"🎯 *TP:* `{next_support:.2f}`"
            )
        else:
            send_telegram_msg(f"❌ *Verification Failed! Trade Skipped.*\n*Reason:* {', '.join(reasons)}")

async def main_loop():
    send_telegram_msg("🤖 *BTC/USDT MEXC SMC Breakout Scanner Started on Railway!*")
    last_processed_time = None

    while True:
        try:
            df = fetch_mexc_klines(limit=50)
            if df is not None and not df.empty:
                current_candle_time = df.iloc[-1]['open_time']
                
                # Check if a new 15m candle has closed
                if last_processed_time != current_candle_time:
                    last_processed_time = current_candle_time
                    analyze_candle(df)

            # Polling every 15 seconds
            await asyncio.sleep(15)

        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main_loop())
