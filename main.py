import ccxt.async_support as ccxt_async
import asyncio
import requests

# ==========================================
# 1. CREDENTIALS & CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = '8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs'
TELEGRAM_CHAT_ID = '8013586305'

MIN_NET_PROFIT_PCT = 0.05  # Minimum profit percentage threshold
DEFAULT_FEE = 0.001        # 0.1% Standard Spot Fee

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram Alert Error:", e)

# ==========================================
# 2. SAFE CROSS-PAIR SCANNER
# ==========================================
async def scan_cross_pair(ex1, ex2, symbol, ex1_name, ex2_name):
    try:
        # Rate limit safety ke liye continuous fetching with exception handling
        t1 = await ex1.fetch_ticker(symbol)
        t2 = await ex2.fetch_ticker(symbol)

        if not (t1 and t2 and t1.get('ask') and t1.get('bid') and t2.get('ask') and t2.get('bid')):
            return None

        start_capital = 100.0

        # --- ROUTE A: Buy EX1 (MEXC), Sell EX2 (Gate.io) ---
        buy_a, sell_a = t1['ask'], t2['bid']
        coins_a = (start_capital / buy_a) * (1 - DEFAULT_FEE)
        return_a = (coins_a * sell_a) * (1 - DEFAULT_FEE)
        profit_a_pct = ((return_a - start_capital) / start_capital) * 100

        if profit_a_pct >= MIN_NET_PROFIT_PCT:
            return {
                'buy_ex': ex1_name, 'sell_ex': ex2_name,
                'symbol': symbol, 'buy_price': buy_a, 'sell_price': sell_a,
                'net_profit_pct': profit_a_pct,
                'net_profit_usdt': return_a - start_capital,
                'final_usdt': return_a
            }

        # --- ROUTE B: Buy EX2 (Gate.io), Sell EX1 (MEXC) ---
        buy_b, sell_b = t2['ask'], t1['bid']
        coins_b = (start_capital / buy_b) * (1 - DEFAULT_FEE)
        return_b = (coins_b * sell_b) * (1 - DEFAULT_FEE)
        profit_b_pct = ((return_b - start_capital) / start_capital) * 100

        if profit_b_pct >= MIN_NET_PROFIT_PCT:
            return {
                'buy_ex': ex2_name, 'sell_ex': ex1_name,
                'symbol': symbol, 'buy_price': buy_b, 'sell_price': sell_b,
                'net_profit_pct': profit_b_pct,
                'net_profit_usdt': return_b - start_capital,
                'final_usdt': return_b
            }

    except Exception:
        # Ignore individual pair errors to keep loop running uninterrupted
        pass
    return None

# ==========================================
# 3. MAIN RUNNER (CRASH PROOF)
# ==========================================
async def main():
    mexc = ccxt_async.mexc({'enableRateLimit': True, 'timeout': 10000})
    gate = ccxt_async.gateio({'enableRateLimit': True, 'timeout': 10000})

    send_telegram_alert("🚀 <b>Crash-Proof Engine Starting...</b>\nEstablishing secure connections...")

    while True:
        try:
            # Re-fetch markets in case of reconnection
            mexc_markets = await mexc.load_markets()
            gate_markets = await gate.load_markets()

            mexc_symbols = {s for s in mexc_markets if s.endswith('/USDT') and mexc_markets[s].get('spot')}
            gate_symbols = {s for s in gate_markets if s.endswith('/USDT') and gate_markets[s].get('spot')}
            
            common_symbols = list(mexc_symbols.intersection(gate_symbols))
            send_telegram_alert(f"✅ <b>Active!</b> Scanning {len(common_symbols)} common spot markets...")

            scan_counter = 0
            BATCH_SIZE = 5  # Reduced batch size to prevent IP blocking/Rate limits

            while True:
                scan_counter += 1

                for i in range(0, len(common_symbols), BATCH_SIZE):
                    batch = common_symbols[i:i + BATCH_SIZE]
                    tasks = [scan_cross_pair(mexc, gate, sym, "MEXC", "Gate.io") for sym in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for res in results:
                        if isinstance(res, dict) and res:
                            msg = (
                                f"🚨 <b>MEXC vs GATE.IO ARBITRAGE!</b>\n\n"
                                f"📌 <b>Pair:</b> {res['symbol']}\n"
                                f"🟢 <b>BUY on {res['buy_ex']}:</b> ${res['buy_price']:.4f}\n"
                                f"🔴 <b>SELL on {res['sell_ex']}:</b> ${res['sell_price']:.4f}\n\n"
                                f"📈 <b>Net Profit:</b> +{res['net_profit_pct']:.3f}%\n"
                                f"💰 <b>Pure Profit ($100):</b> +${res['net_profit_usdt']:.3f}\n"
                                f"⚡ <i>Fees Deducted!</i>"
                            )
                            send_telegram_alert(msg)

                    await asyncio.sleep(0.3)  # Small throttle delay for safety

                if scan_counter % 10 == 0:
                    send_telegram_alert(f"📊 <b>System Update:</b> Active. Total Scanned Cycles: {scan_counter}")

        except Exception as main_err:
            print("Temporary Connection Drop:", main_err)
            # Send alert only on actual crash event & auto-restart loop
            send_telegram_alert(f"⚠️ <b>Network Re-connecting:</b> {main_err}")
            await asyncio.sleep(5)  # Wait 5 sec before reconnecting
        finally:
            await mexc.close()
            await gate.close()
            # Re-instantiate CCXT objects on restart
            mexc = ccxt_async.mexc({'enableRateLimit': True, 'timeout': 10000})
            gate = ccxt_async.gateio({'enableRateLimit': True, 'timeout': 10000})

if __name__ == "__main__":
    asyncio.run(main())
    
