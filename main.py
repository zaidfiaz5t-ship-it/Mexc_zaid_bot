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
        coin_a = start_usdt / t1['ask']
        coin_b = coin_a * t2['bid']
        final_usdt = coin_b * t3['bid']
        
        profit_pct = ((final_usdt - start_usdt) / start_usdt) * 100
        
        if profit_pct >= min_margin:
            return {
                'loop': f"{pair1} -> {pair2} -> {pair3}",
                'margin': profit_pct,
                'return': final_usdt
            }
        return None
    except Exception:
        return None

async def main():
    mexc = ccxt_async.mexc({'apiKey': MEXC_API_KEY, 'secret': MEXC_SECRET_KEY, 'enableRateLimit': False})
    
    loops = [
        ('XRP/USDT', 'XRP/BTC', 'BTC/USDT'),
        ('LTC/USDT', 'LTC/BTC', 'BTC/USDT'),
        ('ADA/USDT', 'ADA/BTC', 'BTC/USDT'),
        ('DOT/USDT', 'DOT/BTC', 'BTC/USDT'),
        ('DOGE/USDT', 'DOGE/BTC', 'BTC/USDT'),
        ('SOL/USDT', 'SOL/BTC', 'BTC/USDT'),
        ('ETH/USDT', 'ETH/BTC', 'BTC/USDT'),
    ]
    
    MIN_TARGET_MARGIN = 0.05
    
    send_telegram_alert("🚀 <b>Arbitrage Cloud Bot Started on Railway!</b>\nMonitoring MEXC 24/7...")
    print("Bot started successfully on Railway!")

    try:
        while True:
            tasks = [scan_loop(mexc, p1, p2, p3, MIN_TARGET_MARGIN) for p1, p2, p3 in loops]
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res:
                    msg = (
                        f"🚨 <b>ARBITRAGE OPPORTUNITY FOUND!</b>\n\n"
                        f"🔄 <b>Loop:</b> {res['loop']}\n"
                        f"📈 <b>Net Profit:</b> +{res['margin']:.3f}%\n"
                        f"💵 <b>Expected Return ($100):</b> ${res['return']:.3f}"
                    )
                    send_telegram_alert(msg)
                    print("Alert Sent to Telegram!")
                    
            await asyncio.sleep(0.3)
    except Exception as e:
        print("Stopped:", e)
    finally:
        await mexc.close()

if __name__ == "__main__":
    asyncio.run(main())
    
