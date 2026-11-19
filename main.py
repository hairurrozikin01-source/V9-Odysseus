
import json
import urllib.request
from datetime import datetime, timezone

API = "https://data-api.binance.vision/api/v3/ticker/24hr"

MEME_COINS = {
    "DOGEUSDT", "SHIBUSDT", "PEPEUSDT",
    "BONKUSDT", "FLOKIUSDT", "WIFUSDT",
    "BOMEUSDT", "MEMEUSDT", "TURBOUSDT",
    "NEIROUSDT", "1000SATSUSDT", "1000RATSUSDT",
    "PONKEUSDT", "DOGSUSDT", "ACTUSDT",
    "BRETTUSDT", "MOGUSDT"
}

def get_data():
    req = urllib.request.Request(
        API,
        headers={"User-Agent": "V9-Odysseus/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def run_v9():
    print("=== V9 MEME COIN SCANNER V2 ===")
    print("Waktu UTC:", datetime.now(timezone.utc))

    data = get_data()
    found = []

    for coin in data:
        symbol = coin["symbol"]

        if symbol not in MEME_COINS:
            continue

        price_change = float(coin["priceChangePercent"])
        volume = float(coin["quoteVolume"])

        if volume < 1000000:
            status = "HINDARI - VOLUME RENDAH"
        elif 2 <= price_change <= 15:
            status = "PANTAU"
        elif price_change > 15:
            status = "WASPADA - SUDAH NAIK"
        else:
            status = "TUNGGU"

        found.append({
            "symbol": symbol,
            "change": price_change,
            "volume": volume,
            "price": coin["lastPrice"],
            "status": status
        })

    found.sort(key=lambda x: x["volume"], reverse=True)

    if not found:
        print("Belum ada pasangan meme coin yang ditemukan.")

    for coin in found:
        print(
            coin["symbol"],
            "| Harga:", coin["price"],
            "| Perubahan:", round(coin["change"], 2), "%",
            "| Volume USDT:", round(coin["volume"]),
            "| Status:", coin["status"]
        )

    print("\nJumlah meme coin ditemukan:", len(found))
    print("MODE: READ ONLY")
    print("Tidak melakukan transaksi.")

if __name__ == "__main__":
    try:
        run_v9()
    except Exception as e:
        print("ERROR:", repr(e))
        raise
        
    
      
