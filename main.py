
import json
import urllib.request
from datetime import datetime, timezone

API = "https://data-api.binance.vision/api/v3/ticker/24hr"

def get_market_data():
    req = urllib.request.Request(
        API,
        headers={"User-Agent": "V9-Odysseus/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())

def run_v9():
    print("=== V9 ODYSSEUS CRYPTO SCANNER ===")
    print("Waktu UTC:", datetime.now(timezone.utc))

    data = get_market_data()

    excluded = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")

    coins = [
        c for c in data
        if c["symbol"].endswith("USDT")
        and not c["symbol"].endswith(excluded)
        and float(c["quoteVolume"]) >= 1000000
    ]

    coins.sort(
        key=lambda c: float(c["quoteVolume"]),
        reverse=True
    )

    print("\n=== KANDIDAT BINANCE SPOT ===")

    count = 0

    for c in coins:
        change = float(c["priceChangePercent"])
        volume = float(c["quoteVolume"])

        if change >= 2 and change <= 15 and volume >= 5000000:
            status = "PANTAU"
        elif change > 0 and change <= 15:
            status = "TUNGGU"
        else:
            status = "HINDARI"

        print(
            c["symbol"],
            "| Harga:", c["lastPrice"],
            "| Perubahan:", round(change, 2), "%",
            "| Volume USDT:", round(volume),
            "| Status:", status
        )

        count += 1
        if count >= 20:
            break

    print("\nTotal pasangan memenuhi filter:", len(coins))
    print("MODE: READ ONLY")
    print("Tidak melakukan transaksi.")

if __name__ == "__main__":
    try:
        run_v9()
    except Exception as e:
        print("ERROR:", repr(e))
        raise
    
      
