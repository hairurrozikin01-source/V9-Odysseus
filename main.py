
import json
import urllib.request
import urllib.parse
import time
from datetime import datetime, timezone

BASE_URL = "https://data-api.binance.vision/api/v3/klines"

# Daftar meme coin Binance Spot untuk pemantauan awal
COINS = [
    "DOGEUSDT",
    "PEPEUSDT",
    "BONKUSDT",
    "SHIBUSDT",
    "FLOKIUSDT",
    "WIFUSDT",
    "BOMEUSDT",
    "MEMEUSDT",
    "TURBOUSDT",
    "NEIROUSDT",
    "1000SATSUSDT",
    "ACTUSDT"
]

def get_candles(symbol):
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "1h",
        "limit": 30
    })

    req = urllib.request.Request(
        BASE_URL + "?" + params,
        headers={"User-Agent": "V9-Odysseus/4.0"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())

def analyze_coin(symbol):
    candles = get_candles(symbol)

    if len(candles) < 27:
        return None

    # Abaikan candle yang masih berjalan
    last = candles[-2]
    previous = candles[-26:-2]

    last_volume = float(last[7])
    last_trades = int(last[8])

    avg_volume = sum(float(c[7]) for c in previous) / 24
    avg_trades = sum(int(c[8]) for c in previous) / 24

    if avg_volume <= 0 or avg_trades <= 0:
        return None

    volume_ratio = last_volume / avg_volume
    trade_ratio = last_trades / avg_trades

    open_price = float(last[1])
    close_price = float(last[4])

    price_change = ((close_price / open_price) - 1) * 100

    score = 0

    if volume_ratio >= 1.5:
        score += 40
    if trade_ratio >= 1.3:
        score += 30
    if price_change >= 0.2:
        score += 15
    if price_change <= 5:
        score += 15

    if volume_ratio >= 1.5 and trade_ratio >= 1.3:
        status = "RADAR AWAL"
    elif volume_ratio >= 1.2 or trade_ratio >= 1.2:
        status = "PANTAU"
    else:
        status = "BELUM ADA SINYAL"

    return {
        "symbol": symbol,
        "price": close_price,
        "change": price_change,
        "volume_ratio": volume_ratio,
        "trade_ratio": trade_ratio,
        "score": score,
        "status": status
    }

def run_v9():
    print("=== V9 ODYSSEUS EARLY PUMP V4 ===")
    print("Waktu UTC:", datetime.now(timezone.utc).isoformat())
    print("Mode: READ ONLY")
    print("Timeframe: 1H")
    print("Pembanding: Rata-rata 24 candle sebelumnya")

    results = []

    for symbol in COINS:
        try:
            result = analyze_coin(symbol)
            if result:
                results.append(result)
        except Exception as error:
            print(symbol, "ERROR:", str(error))

        time.sleep(0.2)

    results.sort(key=lambda x: x["score"], reverse=True)

    print("\n=== HASIL PEMINDAIAN ===")

    for coin in results:
        print(
            coin["symbol"],
            "| Harga:", coin["price"],
            "| Perubahan 1H:", round(coin["change"], 2), "%",
            "| Rasio volume:", round(coin["volume_ratio"], 2), "x",
            "| Rasio transaksi:", round(coin["trade_ratio"], 2), "x",
            "| Skor:", coin["score"],
            "| Status:", coin["status"]
        )

    print("\n=== SELESAI ===")
    print("Tidak ada transaksi otomatis.")

if __name__ == "__main__":
    run_v9()
    
                             
        
    
      
