
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ==========================================
# V9 ODYSSEUS SMART CONFIRMATION V4.2
# ==========================================

VERSION = "V4.2"
INTERVAL = "1h"
CANDLE_LIMIT = 30

# Filter rata-rata volume per jam dalam USDT
MIN_AVG_VOLUME = 10000

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
    "ACTUSDT",
    "PENGUUSDT"
]

API_URLS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
    "https://api1.binance.com/api/v3/klines",
    "https://api2.binance.com/api/v3/klines"
]


# ==========================================
# WAKTU CANDLE
# ==========================================

def format_time(timestamp):

    return datetime.fromtimestamp(
        timestamp / 1000,
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")


# ==========================================
# AMBIL DATA BINANCE
# ==========================================

def get_candles(symbol):

    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": INTERVAL,
        "limit": CANDLE_LIMIT
    })

    errors = []

    for base_url in API_URLS:

        url = base_url + "?" + params

        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "V9-Odysseus/4.2",
                    "Accept": "application/json"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=15
            ) as response:

                data = json.loads(
                    response.read().decode("utf-8")
                )

                if not isinstance(data, list):
                    raise ValueError("Format data tidak valid")

                if len(data) < 27:
                    raise ValueError("Data candle kurang")

                return data

        except urllib.error.HTTPError as error:

            errors.append(
                "HTTP " + str(error.code)
            )

        except Exception as error:

            errors.append(str(error)[:80])

    print(
        symbol,
        "GAGAL MENGAMBIL DATA:",
        " | ".join(errors[-3:])
    )

    return None


# ==========================================
# RATA-RATA
# ==========================================

def average(values):

    if not values:
        return 0

    return sum(values) / len(values)


# ==========================================
# ANALISIS COIN
# ==========================================

def analyze_coin(symbol):

    candles = get_candles(symbol)

    if not candles:
        return None

    # Abaikan candle yang masih berjalan
    current = candles[-2]
    previous = candles[-3]

    # 24 candle sebelum masing-masing candle
    baseline_now = candles[-26:-2]
    baseline_previous = candles[-27:-3]

    avg_volume_now = average([
        float(c[7]) for c in baseline_now
    ])

    avg_volume_previous = average([
        float(c[7]) for c in baseline_previous
    ])

    avg_trades_now = average([
        int(c[8]) for c in baseline_now
    ])

    avg_trades_previous = average([
        int(c[8]) for c in baseline_previous
    ])

    if (
        avg_volume_now <= 0
        or avg_volume_previous <= 0
        or avg_trades_now <= 0
        or avg_trades_previous <= 0
    ):
        return None

    # Volume dalam USDT
    volume_now = float(current[7])
    volume_previous = float(previous[7])

    # Filter aktivitas minimum
    if avg_volume_now < MIN_AVG_VOLUME:
        return {
            "symbol": symbol,
            "status": "HINDARI - VOLUME RENDAH",
            "score": 0,
            "price": float(current[4]),
            "change": 0,
            "volume_ratio": 0,
            "trade_ratio": 0
        }

    # Rasio volume
    vol_now = volume_now / avg_volume_now

    vol_previous = (
        volume_previous / avg_volume_previous
    )

    # Rasio jumlah transaksi
    trades_now = (
        int(current[8]) / avg_trades_now
    )

    trades_previous = (
        int(previous[8]) / avg_trades_previous
    )

    # Harga
    open_now = float(current[1])
    close_now = float(current[4])

    open_previous = float(previous[1])
    close_previous = float(previous[4])

    if open_now <= 0 or open_previous <= 0:
        return None

    # Perubahan harga dua candle
    change_now = (
        close_now / open_now - 1
    ) * 100

    change_previous = (
        close_previous / open_previous - 1
    ) * 100

    # ======================================
    # SISTEM SKOR 0-100
    # ======================================

    score = 0

    # Volume candle terbaru
    if vol_now >= 1.5:
        score += 25
    elif vol_now >= 1.2:
        score += 15

    # Volume candle sebelumnya
    if vol_previous >= 1.2:
        score += 15

    # Jumlah transaksi terbaru
    if trades_now >= 1.3:
        score += 20
    elif trades_now >= 1.1:
        score += 10

    # Jumlah transaksi sebelumnya
    if trades_previous >= 1.1:
        score += 10

    # Arah harga
    if change_now > 0:
        score += 10

    if change_previous > 0:
        score += 10

    # Harga penutupan meningkat
    if close_now > close_previous:
        score += 10

    # ======================================
    # KONFIRMASI DUA CANDLE
    # ======================================

    confirmed = (
        vol_now >= 1.5
        and vol_previous >= 1.2
        and trades_now >= 1.3
        and trades_previous >= 1.1
        and change_now > 0
        and change_previous > 0
        and close_now > close_previous
    )

    if confirmed:

        status = "RADAR AWAL TERKONFIRMASI"

    elif score >= 40 and change_now > 0:

        status = "PANTAU"

    else:

        status = "BELUM ADA SINYAL"

    return {
        "symbol": symbol,
        "price": close_now,
        "change": change_now,
        "previous_change": change_previous,
        "volume_ratio": vol_now,
        "previous_volume_ratio": vol_previous,
        "trade_ratio": trades_now,
        "previous_trade_ratio": trades_previous,
        "avg_hourly_volume": avg_volume_now,
        "score": score,
        "status": status,
        "candle_time": format_time(current[0])
    }


# ==========================================
# MESIN UTAMA
# ==========================================

def run_v9():

    print("======================================")
    print(" V9 ODYSSEUS SMART CONFIRMATION")
    print(" VERSION:", VERSION)
    print("======================================")

    print(
        "Waktu UTC:",
        datetime.now(timezone.utc).isoformat()
    )

    print("Mode: READ ONLY")
    print("Timeframe:", INTERVAL)
    print("Konfirmasi: Dua candle selesai")
    print("Pembanding: 24 candle sebelumnya")
    print("======================================")

    results = []

    for symbol in COINS:

        try:

            result = analyze_coin(symbol)

            if result:
                results.append(result)

        except Exception as error:

            print(
                symbol,
                "ANALISIS ERROR:",
                str(error)
            )

        time.sleep(0.2)

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    print("\n========== HASIL PEMINDAIAN ==========")

    if not results:

        print("Tidak ada data yang berhasil dipindai.")

    for coin in results:

        print("\nCOIN:", coin["symbol"])

        print("Harga:", coin["price"])

        print(
            "Perubahan:",
            round(coin["change"], 2),
            "%"
        )

        print(
            "Rasio volume:",
            round(coin["volume_ratio"], 2),
            "x"
        )

        print(
            "Rasio transaksi:",
            round(coin["trade_ratio"], 2),
            "x"
        )

        print("Skor:", coin["score"], "/ 100")

        print("Status:", coin["status"])

        if "candle_time" in coin:
            print("Candle:", coin["candle_time"])

    # ======================================
    # RINGKASAN
    # ======================================

    confirmed = [
        c for c in results
        if c["status"] == "RADAR AWAL TERKONFIRMASI"
    ]

    watch = [
        c for c in results
        if c["status"] == "PANTAU"
    ]

    print("\n========== RINGKASAN V9 ==========")

    print("Total hasil:", len(results))

    print("Radar awal:", len(confirmed))

    print("Dalam pantauan:", len(watch))

    if confirmed:

        print("\nKANDIDAT RADAR AWAL:")

        for coin in confirmed:
            print(
                coin["symbol"],
                "| Skor:",
                coin["score"]
            )

    else:

        print("\nBelum ada radar awal terkonfirmasi.")

    print("\nMODE: READ ONLY")
    print("Tidak melakukan transaksi.")
    print("V9 SCAN SELESAI.")


# ==========================================
# JALANKAN V9
# ==========================================

if __name__ == "__main__":

    try:
        run_v9()

    except Exception as error:

        print("FATAL ERROR:", repr(error))
        raise
                
