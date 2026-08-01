import ccxt.async_support as ccxt_async
import asyncio
import requests

# ==========================================
# 1. API KEYS & CREDENTIALS
# ==========================================
# Insert your NEW Read-Only Keys here
# Replace this line in main():
binance = ccxt_async.binance({
    'enableRateLimit': True,
    'timeout': 15000
})


MEXC_API_KEY = 'mx0vglAfCE8tKXscOi'
MEXC_SECRET_KEY = '5591ea266c5141bcbfe5f37782c84ac2'

TELEGRAM_BOT_TOKEN = '8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs'
TELEGRAM_CHAT_ID = '8013586305'

# ==========================================
# 2. CONFIGURATION PARAMETERS
# ==========================================
MIN_NET_PROFIT_PCT = 0.05  # Minimum profit percentage after fees
DEFAULT_FEE = 0.001        # 0.1% Standard Spot Fee

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram Alert Error:", e)

# ==========================================
# 3. BULK CROSS-EXCHANGE SCANNER ENGINE
# ==========================================
async def main():
    binance = ccxt_async.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_SECRET_KEY,
        'enableRateLimit': True,
        'timeout': 15000
    })
    
    mexc = ccxt_async.mexc({
        'apiKey': MEXC_API_KEY,
        'secret': MEXC_SECRET_KEY,
        'enableRateLimit': True,
        'timeout': 15000
    })

    send_telegram_alert("🚀 <b>Authenticated Cross-Scanner Active!</b>\nConnected to Binance & MEXC via API Keys.")

    try:
        binance_markets, mexc_markets = await asyncio.gather(
            binance.load_markets(),
            mexc.load_markets()
        )

        binance_symbols = {s for s in binance_markets if s.endswith('/USDT') and binance_markets[s].get('spot')}
        mexc_symbols = {s for s in mexc_markets if s.endswith('/USDT') and mexc_markets[s].get('spot')}
        
        common_symbols = list(binance_symbols.intersection(mexc_symbols))

        send_telegram_alert(f"✅ <b>Setup Complete!</b>\nMonitoring <b>{len(common_symbols)} Common Spot Pairs</b> between Binance & MEXC.")
        print(f"Loaded {len(common_symbols)} common spot pairs.")

        scan_counter = 0

        while True:
            scan_counter += 1
            try:
                binance_tickers, mexc_tickers = await asyncio.gather(
                    binance.fetch_tickers(common_symbols),
                    mexc.fetch_tickers(common_symbols),
                    return_exceptions=True
                )

                if isinstance(binance_tickers, Exception) or isinstance(mexc_tickers, Exception):
                    await asyncio.sleep(2)
                    continue

                for symbol in common_symbols:
                    t1 = binance_tickers.get(symbol)
                    t2 = mexc_tickers.get(symbol)

                    if not (t1 and t2 and t1.get('ask') and t1.get('bid') and t2.get('ask') and t2.get('bid')):
                        continue

                    start_capital = 100.0  # $100 basis

                    # --- ROUTE A: Buy Binance, Sell MEXC ---
                    buy_a, sell_a = t1['ask'], t2['bid']
                    if buy_a > 0:
                        coins_a = (start_capital / buy_a) * (1 - DEFAULT_FEE)
                        return_a = (coins_a * sell_a) * (1 - DEFAULT_FEE)
                        profit_a_pct = ((return_a - start_capital) / start_capital) * 100

                        if profit_a_pct >= MIN_NET_PROFIT_PCT:
                            msg = (
                                f"🚨 <b>BINANCE ➔ MEXC ARBITRAGE!</b>\n\n"
                                f"📌 <b>Pair:</b> {symbol}\n"
                                f"🟢 <b>BUY on Binance:</b> ${buy_a:.4f}\n"
                                f"🔴 <b>SELL on MEXC:</b> ${sell_a:.4f}\n\n"
                                f"📈 <b>Net Profit:</b> +{profit_a_pct:.3f}%\n"
                                f"💰 <b>Est. Pure Profit ($100):</b> +${(return_a - start_capital):.3f}\n"
                                f"💵 <b>Expected Return:</b> ${return_a:.3f}\n\n"
                                f"⚡ <i>Fees Deducted! Execute manually.</i>"
                            )
                            send_telegram_alert(msg)

                    # --- ROUTE B: Buy MEXC, Sell Binance ---
                    buy_b, sell_b = t2['ask'], t1['bid']
                    if buy_b > 0:
                        coins_b = (start_capital / buy_b) * (1 - DEFAULT_FEE)
                        return_b = (coins_b * sell_b) * (1 - DEFAULT_FEE)
                        profit_b_pct = ((return_b - start_capital) / start_capital) * 100

                        if profit_b_pct >= MIN_NET_PROFIT_PCT:
                            msg = (
                                f"🚨 <b>MEXC ➔ BINANCE ARBITRAGE!</b>\n\n"
                                f"📌 <b>Pair:</b> {symbol}\n"
                                f"🟢 <b>BUY on MEXC:</b> ${buy_b:.4f}\n"
                                f"🔴 <b>SELL on Binance:</b> ${sell_b:.4f}\n\n"
                                f"📈 <b>Net Profit:</b> +{profit_b_pct:.3f}%\n"
                                f"💰 <b>Est. Pure Profit ($100):</b> +${(return_b - start_capital):.3f}\n"
                                f"💵 <b>Expected Return:</b> ${return_b:.3f}\n\n"
                                f"⚡ <i>Fees Deducted! Execute manually.</i>"
                            )
                            send_telegram_alert(msg)

                if scan_counter % 20 == 0:
                    send_telegram_alert(f"📊 <b>System Update:</b> Scanner Active. Total Scans Completed: <b>{scan_counter}</b>")

                await asyncio.sleep(2)

            except Exception as loop_e:
                await asyncio.sleep(2)

    except Exception as fatal_e:
        send_telegram_alert(f"⚠️ <b>Engine Alert:</b> {fatal_e}")
    finally:
        await binance.close()
        await mexc.close()

if __name__ == "__main__":
    asyncio.run(main())
    
