
import json
import urllib.request
import urllib.parse
import time
from datetime import datetime, timezone

BASE_URL = "https://data-api.binance.vision/api/v3/klines"

COINS = [
    "DOGEUSDT", "PEPEUSDT", "BONKUSDT",
    "SHIBUSDT", "FLOKIUSDT", "WIFUSDT",
    "BOMEUSDT", "MEMEUSDT", "TURBOUSDT",
    "NEIROUSDT", "1000SATSUSDT", "ACTUSDT"
]

def get_candles(symbol):
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "1h",
        "limit": 30
    })

    req = urllib.request.Request(
        BASE_URL + "?" + params,
        headers={"User-Agent": "V9-Odysseus/4.1"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())

def analyze_coin(symbol):
    candles = get_candles(symbol)

    if len(candles) < 28:
        return None

    # Dua candle terakhir yang sudah selesai
    current = candles[-2]
    previous = candles[-3]

    # 24 candle sebelum dua candle tersebut
    baseline = candles[-27:-3]

    avg_volume = sum(float(c[7]) for c in baseline) / 24
    avg_trades = sum(int(c[8]) for c in baseline) / 24

    if avg_volume <= 0 or avg_trades <= 0:
        return None

    vol_now = float(current[7]) / avg_volume
    vol_previous = float(previous[7]) / avg_volume

    trades_now = int(current[8]) / avg_trades
    trades_previous = int(previous[8]) / avg_trades

    open_now = float(current[1])
    close_now = float(current[4])
    close_previous = float(previous[4])

    change_now = (close_now / open_now - 1) * 100
    change_previous = (
        close_now / close_previous - 1
    ) * 100

    
    score = 0

    if vol_now >= 1.5:
        score += 25
    elif vol_now >= 1.2:
        score += 15

    if vol_previous >= 1.2:
        score += 15

    if trades_now >= 1.3:
        score += 25
    elif trades_now >= 1.1:
        score += 15

    if trades_previous >= 1.1:
        score += 15

    if change_now > 0:
        score += 10

    if change_previous > 0:
        score += 10

    confirmed = (
        vol_now >= 1.5
        and vol_previous >= 1.2
        and trades_now >= 1.3
        and trades_previous >= 1.1
        and change_now > 0
        and change_previous > 0
    )

    if confirmed:
        status = "RADAR AWAL TERKONFIRMASI"
    else:
        score = min(score, 79)

        if (
            (vol_now >= 1.2 or trades_now >= 1.1)
            and change_now > 0
        ):
            status = "PANTAU"
        else:
            status = "BELUM ADA SINYAL"
    return {
        "symbol": symbol,
        "price": close_now,
        "change": change_now,
        "volume": vol_now,
        "previous_volume": vol_previous,
        "trades": trades_now,
        "previous_trades": trades_previous,
        "score": score,
        "status": status
    }

def run_v9():
    print("=== V9 ODYSSEUS SMART CONFIRMATION V4.1 ===")
    print("UTC:", datetime.now(timezone.utc).isoformat())
    print("Mode: READ ONLY")
    print("Konfirmasi: Dua candle 1H")

    results = []

    for symbol in COINS:
        try:
            result = analyze_coin(symbol)
            if result:
                results.append(result)
        except Exception as error:
            print(symbol, "ERROR:", str(error))

        time.sleep(0.2)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    print("\n=== HASIL PEMINDAIAN ===")

    for coin in results:
        print(
            coin["symbol"],
            "| Harga:", coin["price"],
            "| Perubahan:", round(coin["change"], 2), "%",
            "| Volume:", round(coin["volume"], 2), "x",
            "| Volume sebelumnya:",
            round(coin["previous_volume"], 2), "x",
            "| Transaksi:", round(coin["trades"], 2), "x",
            "| Transaksi sebelumnya:",
            round(coin["previous_trades"], 2), "x",
            "| Skor:", coin["score"],
            "| Status:", coin["status"]
        )

    print("\n=== PEMINDAIAN SELESAI ===")
    print("Tidak ada transaksi otomatis.")

if __name__ == "__main__":
    run_v9()
    
                             
        
    
      
