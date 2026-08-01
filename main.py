import ccxt.async_support as ccxt_async
import asyncio
import requests

# ==========================================
# 1. CREDENTIALS & CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = '8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs'
TELEGRAM_CHAT_ID = '8013586305'

# Minimum Net Profit threshold after deducting ALL fees (in %)
MIN_NET_PROFIT_PCT = 0.05  

# Default Trading Fees (0.1% per trade)
DEFAULT_FEE = 0.001 

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram Alert Error:", e)

# ==========================================
# 2. CROSS-EXCHANGE SCANNER ENGINE
# ==========================================
async def scan_cross_pair(ex1, ex2, symbol, ex1_name, ex2_name):
    try:
        t1, t2 = await asyncio.gather(
            ex1.fetch_ticker(symbol),
            ex2.fetch_ticker(symbol)
        )

        if not (t1.get('ask') and t1.get('bid') and t2.get('ask') and t2.get('bid')):
            return None

        start_capital = 100.0  # $100 USDT basis

        # --- ROUTE A: Buy on EX1 (MEXC), Sell on EX2 (Gate.io) ---
        buy_price_a = t1['ask']
        sell_price_a = t2['bid']
        
        coins_a = (start_capital / buy_price_a) * (1 - DEFAULT_FEE)
        return_a = (coins_a * sell_price_a) * (1 - DEFAULT_FEE)
        profit_a_pct = ((return_a - start_capital) / start_capital) * 100

        if profit_a_pct >= MIN_NET_PROFIT_PCT:
            return {
                'buy_ex': ex1_name,
                'sell_ex': ex2_name,
                'symbol': symbol,
                'buy_price': buy_price_a,
                'sell_price': sell_price_a,
                'net_profit_pct': profit_a_pct,
                'net_profit_usdt': return_a - start_capital,
                'final_usdt': return_a
            }

        # --- ROUTE B: Buy on EX2 (Gate.io), Sell on EX1 (MEXC) ---
        buy_price_b = t2['ask']
        sell_price_b = t1['bid']

        coins_b = (start_capital / buy_price_b) * (1 - DEFAULT_FEE)
        return_b = (coins_b * sell_price_b) * (1 - DEFAULT_FEE)
        profit_b_pct = ((return_b - start_capital) / start_capital) * 100

        if profit_b_pct >= MIN_NET_PROFIT_PCT:
            return {
                'buy_ex': ex2_name,
                'sell_ex': ex1_name,
                'symbol': symbol,
                'buy_price': buy_price_b,
                'sell_price': sell_price_b,
                'net_profit_pct': profit_b_pct,
                'net_profit_usdt': return_b - start_capital,
                'final_usdt': return_b
            }

        return None

    except Exception:
        return None

# ==========================================
# 3. MAIN RUNNER
# ==========================================
async def main():
    mexc = ccxt_async.mexc({'enableRateLimit': True})
    gate = ccxt_async.gateio({'enableRateLimit': True})

    send_telegram_alert("🚀 <b>Cross-Exchange Engine (MEXC vs Gate.io) Initializing...</b>\nFetching common spot markets...")

    try:
        mexc_markets, gate_markets = await asyncio.gather(
            mexc.load_markets(),
            gate.load_markets()
        )

        # Common USDT Spot Pairs
        mexc_symbols = {s for s in mexc_markets if s.endswith('/USDT') and mexc_markets[s]['spot']}
        gate_symbols = {s for s in gate_markets if s.endswith('/USDT') and gate_markets[s]['spot']}
        
        common_symbols = list(mexc_symbols.intersection(gate_symbols))

        send_telegram_alert(f"✅ <b>Setup Complete!</b>\nMonitoring <b>{len(common_symbols)} Common Altcoin Pairs</b> between MEXC & Gate.io.\nStarting 24/7 Scan Engine...")
        print(f"Loaded {len(common_symbols)} cross-exchange pairs between MEXC and Gate.io.")

        scan_counter = 0
        BATCH_SIZE = 10

        while True:
            scan_counter += 1

            for i in range(0, len(common_symbols), BATCH_SIZE):
                batch = common_symbols[i:i + BATCH_SIZE]
                tasks = [scan_cross_pair(mexc, gate, sym, "MEXC", "Gate.io") for sym in batch]
                results = await asyncio.gather(*tasks)

                for res in results:
                    if res:
                        msg = (
                            f"🚨 <b>MEXC vs GATE.IO ARBITRAGE!</b>\n\n"
                            f"📌 <b>Pair:</b> {res['symbol']}\n"
                            f"🟢 <b>BUY on {res['buy_ex']}:</b> ${res['buy_price']:.4f}\n"
                            f"🔴 <b>SELL on {res['sell_ex']}:</b> ${res['sell_price']:.4f}\n\n"
                            f"📈 <b>Net Profit:</b> +{res['net_profit_pct']:.3f}%\n"
                            f"💰 <b>Est. Pure Profit ($100):</b> +${res['net_profit_usdt']:.3f}\n"
                            f"💵 <b>Final Total ($100):</b> ${res['final_usdt']:.3f}\n\n"
                            f"⚡ <i>Fees deducted. Trade quickly!</i>"
                        )
                        send_telegram_alert(msg)

                await asyncio.sleep(0.1)

            if scan_counter % 15 == 0:
                send_telegram_alert(f"📊 <b>System Update:</b> MEXC vs Gate.io Scanner Active. Scanned <b>{scan_counter * len(common_symbols)}</b> pair checks.")

    except Exception as e:
        print("Engine Error:", e)
        send_telegram_alert(f"⚠️ <b>Engine Error:</b> {e}")
    finally:
        await mexc.close()
        await gate.close()

if __name__ == "__main__":
    asyncio.run(main())
    
