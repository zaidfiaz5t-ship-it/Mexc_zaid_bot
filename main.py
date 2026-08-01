import ccxt.async_support as ccxt_async
import asyncio
import requests

# ==========================================
# 1. TELEGRAM CREDENTIALS
# ==========================================
TELEGRAM_BOT_TOKEN = '8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs'
TELEGRAM_CHAT_ID = '8013586305'

# ==========================================
# 2. TARGET MEXC PAIRS (Top Volatile / High Spread)
# ==========================================
TARGET_PAIRS = [
    'KAS/USDT',
    'JASMY/USDT',
    'PEPE/USDT',
    'FLOKI/USDT',
    'BONK/USDT',
    'MEW/USDT',
    'NOT/USDT',
    'TURBO/USDT',
    'SHIB/USDT',
    'WIF/USDT'
]

# MEXC Standard Spot Fee (0.1% = 0.001)
MEXC_SPOT_FEE = 0.001  
START_CAPITAL = 100.0  # Baseline $100 calculation

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram Alert Error:", e)

async def main():
    # Only MEXC Exchange connection
    mexc = ccxt_async.mexc({
        'enableRateLimit': True, 
        'timeout': 15000
    })

    send_telegram_alert("🚀 <b>MEXC Internal Spread Engine Online!</b>\nScanning Orderbook gaps for target pairs with exact fee deduction...")

    try:
        while True:
            try:
                # Fetch MEXC tickers
                mexc_tickers = await mexc.fetch_tickers(TARGET_PAIRS)

                for symbol in TARGET_PAIRS:
                    t_mexc = mexc_tickers.get(symbol)

                    if not (t_mexc and t_mexc.get('ask') and t_mexc.get('bid')):
                        continue

                    mexc_ask = float(t_mexc['ask'])  # Lowest price to BUY
                    mexc_bid = float(t_mexc['bid'])  # Highest price to SELL

                    if mexc_ask > 0 and mexc_bid > 0:
                        # 1. Buy coins at Best Ask Price (Deduct 0.1% Fee)
                        coins_bought = (START_CAPITAL / mexc_ask) * (1 - MEXC_SPOT_FEE)
                        
                        # 2. Sell coins at Best Bid Price (Deduct 0.1% Fee)
                        final_usdt = (coins_bought * mexc_bid) * (1 - MEXC_SPOT_FEE)
                        
                        # Calculations
                        gross_gap_pct = ((mexc_bid - mexc_ask) / mexc_ask) * 100
                        net_profit = final_usdt - START_CAPITAL
                        net_profit_pct = (net_profit / START_CAPITAL) * 100

                        msg = (
                            f"📊 <b>MEXC INTERNAL ORDERBOOK SCAN</b>\n"
                            f"📌 <b>Pair:</b> {symbol}\n\n"
                            f"🟢 <b>Best Ask (Buy Price):</b> ${mexc_ask:.6f}\n"
                            f"🔴 <b>Best Bid (Sell Price):</b> ${mexc_bid:.6f}\n"
                            f"📈 <b>Gross Book Spread:</b> {gross_gap_pct:+.3f}%\n\n"
                            f"💵 <b>Initial Capital:</b> ${START_CAPITAL:.2f}\n"
                            f"📉 <b>MEXC Buy Fee (0.1%):</b> Deducted\n"
                            f"📉 <b>MEXC Sell Fee (0.1%):</b> Deducted\n"
                            f"🏁 <b>Final Capital:</b> ${final_usdt:.3f}\n"
                            f"💰 <b>Net P/L:</b> <b>{net_profit:+.3f} USDT ({net_profit_pct:+.3f}%)</b>"
                        )
                        send_telegram_alert(msg)

                await asyncio.sleep(4)  # 4-second scan loop

            except Exception as loop_e:
                await asyncio.sleep(2)

    except Exception as fatal_e:
        send_telegram_alert(f"⚠️ <b>Engine Alert:</b> {fatal_e}")
    finally:
        await mexc.close()

if __name__ == "__main__":
    asyncio.run(main())
