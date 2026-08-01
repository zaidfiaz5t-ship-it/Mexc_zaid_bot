import ccxt.async_support as ccxt_async
import asyncio
import time
import requests

# ==========================================
# 1. CONFIGURATION & CREDENTIALS
# ==========================================
MEXC_API_KEY = 'mx0vglAfCE8tKXscOi'
MEXC_SECRET_KEY = '5591ea266c5141bcbfe5f37782c84ac2'
TELEGRAM_BOT_TOKEN = '8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs'
TELEGRAM_CHAT_ID = '8013586305'

# Minimum Net Profit threshold after deducting ALL fees (in %)
# 0.001% net profit tak ki opportunites bhi alert kar dega
MIN_NET_PROFIT_PCT = 0.001  

# Standard Default Fee if ticker fee missing (0.1%)
DEFAULT_SPOT_FEE = 0.001 

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram Alert Error:", e)

# ==========================================
# 2. DYNAMIC FEE & TICKER SCANNER
# ==========================================
async def scan_dynamic_loop(mexc, pair1, pair2, pair3, fee_map):
    try:
        t1, t2, t3 = await asyncio.gather(
            mexc.fetch_ticker(pair1),
            mexc.fetch_ticker(pair2),
            mexc.fetch_ticker(pair3)
        )
        
        # Validate order book availability
        if not (t1.get('ask') and t2.get('bid') and t3.get('bid')):
            return None

        # Fetch fee rates (0% promo or default spot fee)
        fee1 = fee_map.get(pair1, DEFAULT_SPOT_FEE)
        fee2 = fee_map.get(pair2, DEFAULT_SPOT_FEE)
        fee3 = fee_map.get(pair3, DEFAULT_SPOT_FEE)

        start_usdt = 100.0  # Base Capital

        # Trade 1: USDT -> Coin A
        coin_a = (start_usdt / t1['ask']) * (1 - fee1)
        
        # Trade 2: Coin A -> Coin B
        coin_b = (coin_a * t2['bid']) * (1 - fee2)
        
        # Trade 3: Coin B -> USDT
        final_usdt = (coin_b * t3['bid']) * (1 - fee3)

        # Calculations
        net_profit_usdt = final_usdt - start_usdt
        net_profit_pct = (net_profit_usdt / start_usdt) * 100
        total_fees_pct = (fee1 + fee2 + fee3) * 100

        loop_name = f"{pair1} ➔ {pair2} ➔ {pair3}"

        # If net profit exceeds our positive threshold, dispatch alert
        if net_profit_pct >= MIN_NET_PROFIT_PCT:
            return {
                'loop': loop_name,
                'net_profit_pct': net_profit_pct,
                'net_profit_usdt': net_profit_usdt,
                'final_usdt': final_usdt,
                'total_fees_pct': total_fees_pct
            }
        return None

    except Exception:
        return None

# ==========================================
# 3. MAIN RUNNER & PAIR DISCOVERY
# ==========================================
async def main():
    mexc = ccxt_async.mexc({'apiKey': MEXC_API_KEY, 'secret': MEXC_SECRET_KEY, 'enableRateLimit': False})
    
    send_telegram_alert("🚀 <b>Arbitrage Engine Initializing...</b>\nFetching MEXC markets & fee structures...")
    
    try:
        markets = await mexc.load_markets()
        
        # Build Pair Fee Lookup Map
        fee_map = {}
        for symbol, data in markets.items():
            maker_fee = data.get('maker', DEFAULT_SPOT_FEE)
            taker_fee = data.get('taker', DEFAULT_SPOT_FEE)
            fee_map[symbol] = max(maker_fee, taker_fee)

        # Dynamic Loops Builder (USDT -> ALT -> BTC -> USDT)
        usdt_pairs = [s for s in markets if s.endswith('/USDT') and markets[s]['spot']]
        btc_pairs = [s for s in markets if s.endswith('/BTC') and markets[s]['spot']]
        
        btc_alts = {s.split('/')[0] for s in btc_pairs}
        
        loops = []
        for pair1 in usdt_pairs:
            coin_a = pair1.split('/')[0]
            if coin_a in btc_alts:
                pair2 = f"{coin_a}/BTC"
                pair3 = "BTC/USDT"
                if pair2 in markets and pair3 in markets:
                    loops.append((pair1, pair2, pair3))

        send_telegram_alert(f"✅ <b>Setup Complete!</b>\nDiscovered <b>{len(loops)} Dynamic Arbitrage Loops</b>.\nStarting 24/7 Scan Engine...")
        print(f"Loaded {len(loops)} dynamic triangular loops.")

        scan_counter = 0
        BATCH_SIZE = 15  # Batch execution to maintain stability

        while True:
            scan_counter += 1
            
            # Execute scanner in batches
            for i in range(0, len(loops), BATCH_SIZE):
                batch = loops[i:i + BATCH_SIZE]
                tasks = [scan_dynamic_loop(mexc, p1, p2, p3, fee_map) for p1, p2, p3 in batch]
                results = await asyncio.gather(*tasks)

                for res in results:
                    if res:
                        msg = (
                            f"🚨 <b>REAL ARBITRAGE OPPORTUNITY FOUND!</b>\n\n"
                            f"🔄 <b>Loop:</b> {res['loop']}\n"
                            f"📈 <b>Net Profit:</b> +{res['net_profit_pct']:.4f}%\n"
                            f"💵 <b>Est. Net Return ($100):</b> ${res['final_usdt']:.4f}\n"
                            f"💰 <b>Pure Profit:</b> +${res['net_profit_usdt']:.4f}\n"
                            f"💸 <b>Total Deducted Fees:</b> ~{res['total_fees_pct']:.2f}%\n\n"
                            f"⚡ <i>Prices updated in real-time. Execute fast!</i>"
                        )
                        send_telegram_alert(msg)

                await asyncio.sleep(0.1)

            # Send heartbeat updates every 10 scan cycles
            if scan_counter % 10 == 0:
                total_scans = scan_counter * len(loops)
                send_telegram_alert(f"📊 <b>System Update:</b> Active scanning in progress. Total routes scanned: <b>{total_scans}</b>.")

    except Exception as e:
        print("Engine Error:", e)
        send_telegram_alert(f"⚠️ <b>Engine Warning:</b> {e}")
    finally:
        await mexc.close()

if __name__ == "__main__":
    asyncio.run(main())
        
    
    
