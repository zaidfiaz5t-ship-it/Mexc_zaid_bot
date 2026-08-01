import ccxt.async_support as ccxt_async
import asyncio
import time
import requests
import os

# 1. Credentials
MEXC_API_KEY = 'mx0vglAfCE8tKXscOi'
MEXC_SECRET_KEY = '5591ea266c5141bcbfe5f37782c84ac2'
TELEGRAM_BOT_TOKEN = '8966817934:AAEQCfnoh90Ek-13kOoPJG17oRCfzzCogQs'
TELEGRAM_CHAT_ID = '8013586305'

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram Alert Error:", e)

async def scan_loop(mexc, pair1, pair2, pair3, min_margin):
    try:
        t1, t2, t3 = await asyncio.gather(
            mexc.fetch_ticker(pair1),
            mexc.fetch_ticker(pair2),
            mexc.fetch_ticker(pair3)
        )
        
        start_usdt = 100.0
        
        # Prices validation check
        if not (t1['ask'] and t2['bid'] and t3['bid']):
            return None
            
        coin_a = start_usdt / t1['ask']
        coin_b = coin_a * t2['bid']
        final_usdt = coin_b * t3['bid']
        
        profit_pct = ((final_usdt - start_usdt) / start_usdt) * 100
        
        loop_name = f"{pair1} ➔ {pair2} ➔ {pair3}"
        
        # Real-time console status
        print(f"🔍 Checked [{loop_name}] | Margin: {profit_pct:.4f}%")
        
        if profit_pct >= min_margin:
            return {
                'loop': loop_name,
                'margin': profit_pct,
                'return': final_usdt
            }
        return None
    except Exception as e:
        print(f"Error scanning {pair1}: {e}")
        return None

async def main():
    mexc = ccxt_async.mexc({'apiKey': MEXC_API_KEY, 'secret': MEXC_SECRET_KEY, 'enableRateLimit': False})
    
    # Expanded Market Pairs
    loops = [
        ('XRP/USDT', 'XRP/BTC', 'BTC/USDT'),
        ('LTC/USDT', 'LTC/BTC', 'BTC/USDT'),
        ('ADA/USDT', 'ADA/BTC', 'BTC/USDT'),
        ('DOT/USDT', 'DOT/BTC', 'BTC/USDT'),
        ('DOGE/USDT', 'DOGE/BTC', 'BTC/USDT'),
        ('SOL/USDT', 'SOL/BTC', 'BTC/USDT'),
        ('ETH/USDT', 'ETH/BTC', 'BTC/USDT'),
        ('BCH/USDT', 'BCH/BTC', 'BTC/USDT'),
        ('EOS/USDT', 'EOS/BTC', 'BTC/USDT'),
        ('TRX/USDT', 'TRX/BTC', 'BTC/USDT'),
    ]
    
    # Margin filter (Adjusted to 0.01% so you get alerts on small gaps too)
    MIN_TARGET_MARGIN = 0.01
    
    send_telegram_alert("🔄 <b>Arbitrage Scan Started!</b>\n\nMonitoring 10 Major Pairs on MEXC...")
    print("Bot started with expanded pair scan!")

    try:
        scan_counter = 0
        while True:
            scan_counter += 1
            tasks = [scan_loop(mexc, p1, p2, p3, MIN_TARGET_MARGIN) for p1, p2, p3 in loops]
            results = await asyncio.gather(*tasks)
            
            alerts_found = False
            for res in results:
                if res:
                    alerts_found = True
                    msg = (
                        f"🚨 <b>ARBITRAGE OPPORTUNITY FOUND!</b>\n\n"
                        f"🔄 <b>Loop:</b> {res['loop']}\n"
                        f"📈 <b>Net Profit:</b> +{res['margin']:.3f}%\n"
                        f"💵 <b>Expected Return ($100):</b> ${res['return']:.3f}"
                    )
                    send_telegram_alert(msg)
                    print(f"✅ Alert sent for {res['loop']}")
            
            # Periodic Summary Message on Telegram every 50 scans
            if scan_counter % 50 == 0:
                send_telegram_alert(f"📊 <b>System Update:</b> Bot is active. Scanned {scan_counter * len(loops)} pair routes successfully.")
                
            await asyncio.sleep(1)
    except Exception as e:
        print("Loop stopped:", e)
    finally:
        await mexc.close()

if __name__ == "__main__":
    asyncio.run(main())
    
    
