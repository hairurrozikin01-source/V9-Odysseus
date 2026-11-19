
import json
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode

BASE = "https://data-api.binance.vision"

MEME_COINS = [
    "DOGEUSDT", "SHIBUSDT", "PEPEUSDT",
    "BONKUSDT", "FLOKIUSDT", "WIFUSDT",
    "BOMEUSDT", "MEMEUSDT", "TURBOUSDT",
    "NEIROUSDT", "1000SATSUSDT", "1000RATSUSDT",
    "DOGSUSDT", "ACTUSDT", "BRETTUSDT",
    "MOGUSDT"
]

def get_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "V9-Odysseus/3.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def scan_coin(symbol):
    params = urlencode({
        "symbol": symbol,
        "interval": "1h",
        "limit": 168
    })

    candles = get_json(BASE + "/api/v3/klines?" + params)

    if len(candles) < 168:
        return None

    volumes = [float(c[7]) for c in candles]

    recent_24h = sum(volumes[-24:])
    previous_daily_avg = sum(volumes[-168:-24]) / 6

    ratio = (
        recent_24h / previous_daily_avg
        if previous_daily_avg > 0 else 0
    )

    ticker = get_json(
        BASE + "/api/v3/ticker/24hr?" +
        urlencode({"symbol": symbol})
    )

    change = float(ticker["priceChangePercent"])

    if ratio >= 2 and change > 0 and change <= 15:
        status = "PANTAU"
    elif ratio >= 1.3:
        status = "TUNGGU"
    else:
        status = "HINDARI"

    return {
        "symbol": symbol,
        "change": change,
        "volume": recent_24h,
        "average": previous_daily_avg,
        "ratio": ratio,
        "status": status
    }

def run_v9():
    print("=== V9 VOLUME INTELLIGENCE V3 ===")
    print("Waktu UTC:", datetime.now(timezone.utc))

    results = []

    for symbol in MEME_COINS:
        try:
            result = scan_coin(symbol)

            if result:
                results.append(result)
                print(
                    symbol,
                    "| Perubahan:", round(result["change"], 2), "%",
                    "| Volume 24h:", round(result["volume"]),
                    "| Rata-rata 6 hari:", round(result["average"]),
                    "| Rasio volume:", round(result["ratio"], 2), "x",
                    "| Status:", result["status"]
                )

        except Exception as e:
            print("GAGAL", symbol, repr(e))

    results.sort(key=lambda x: x["ratio"], reverse=True)

    print("\n=== RANKING VOLUME ===")
    for i, coin in enumerate(results[:10], 1):
        print(i, coin["symbol"], coin["ratio"], "x", coin["status"])

    print("\nJumlah berhasil dipindai:", len(results))
    print("MODE: READ ONLY")
    print("Tidak melakukan transaksi.")

if __name__ == "__main__":
    run_v9()
                             
        
    
      
