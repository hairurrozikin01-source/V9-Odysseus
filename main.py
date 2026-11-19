
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
    print("=== V9 ODYSSEUS ENGINE ===")
    print("Waktu UTC:", datetime.now(timezone.utc))

    try:
        data = get_market_data()

        coins = [
            c for c in data
            if c["symbol"].endswith("USDT")
            and float(c["quoteVolume"]) >= 100000
        ]

        coins.sort(
            key=lambda c: float(c["quoteVolume"]),
            reverse=True
        )

        print("\nTOP 10 KOIN BINANCE SPOT")

        for c in coins[:10]:
            print(
                c["symbol"],
                "Perubahan:", c["priceChangePercent"], "%",
                "Volume:", c["quoteVolume"], "USDT"
            )

        print("\nSTATUS: MONITORING BERHASIL")
        print("Mode: READ ONLY")
        print("Tidak melakukan transaksi.")

    except Exception as e:
        print("ERROR:", repr(e))
        raise

if __name__ == "__main__":
    run_v9()
      
