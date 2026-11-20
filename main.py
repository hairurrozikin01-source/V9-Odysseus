
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ==========================================
# V9 ODYSSEUS SMART CONFIRMATION V4.4
# ==========================================

VERSION = "V4.4"
INTERVAL = "1h"
CANDLE_LIMIT = 100
MIN_AVG_VOLUME = 10000
BREAKOUT_LOOKBACK = 20

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
# WAKTU
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
                    "User-Agent": "V9-Odysseus/4.4",
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

                if len(data) < 40:
                    raise ValueError("Data candle kurang")

                return data

        except urllib.error.HTTPError as error:
            errors.append("HTTP " + str(error.code))

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
# EMA ENGINE
# ==========================================

def calculate_ema(values, period):

    if len(values) < period:
        return []

    multiplier = 2 / (period + 1)

    ema = sum(values[:period]) / period
    result = [ema]

    for value in values[period:]:

        ema = (
            value * multiplier
            + ema * (1 - multiplier)
        )

        result.append(ema)

    return result


# ==========================================
# RSI 14
# ==========================================

def calculate_rsi(closes, period=14):

    if len(closes) < period + 1:
        return None

    changes = [
        closes[i] - closes[i - 1]
        for i in range(1, len(closes))
    ]

    gains = [
        max(change, 0)
        for change in changes
    ]

    losses = [
        max(-change, 0)
        for change in changes
    ]

    avg_gain = average(gains[:period])
    avg_loss = average(losses[:period])

    for i in range(period, len(gains)):

        avg_gain = (
            avg_gain * (period - 1)
            + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1)
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ==========================================
# MACD 12 / 26 / 9
# ==========================================

def calculate_macd(closes):

    if len(closes) < 35:
        return None

    ema12 = calculate_ema(closes, 12)
    ema26 = calculate_ema(closes, 26)

    if not ema12 or not ema26:
        return None

    macd_line = [
        fast - slow
        for fast, slow in zip(
            ema12[-len(ema26):],
            ema26
        )
    ]

    signal_line = calculate_ema(macd_line, 9)

    if len(signal_line) < 2:
        return None

    histogram = [
        macd_line[-len(signal_line) + i]
        - signal_line[i]
        for i in range(len(signal_line))
    ]

    return {
        "macd": macd_line[-1],
        "signal": signal_line[-1],
        "histogram": histogram[-1],
        "previous_histogram": histogram[-2],
        "bullish": macd_line[-1] > signal_line[-1],
        "histogram_rising": histogram[-1] > histogram[-2]
    }


# ==========================================
# V4.4 MOMENTUM ENGINE
# ==========================================

def calculate_momentum(candles):

    closed = candles[:-1]

    closes = [
        float(c[4])
        for c in closed
    ]

    if len(closes) < 35:
        return None

    rsi = calculate_rsi(closes, 14)
    macd = calculate_macd(closes)

    if rsi is None or macd is None:
        return None

    # Perubahan harga 3 candle
    recent_roc = (
        closes[-1] / closes[-4] - 1
    ) * 100

    previous_roc = (
        closes[-4] / closes[-7] - 1
    ) * 100

    acceleration = recent_roc - previous_roc

    # Skor momentum 0-30
    momentum_score = 0

    if 50 < rsi < 70:
        momentum_score += 10

    elif rsi >= 70:
        momentum_score += 5

    if macd["bullish"]:
        momentum_score += 10

    if macd["histogram_rising"]:
        momentum_score += 5

    if acceleration > 0:
        momentum_score += 5

    momentum_bullish = (
        rsi > 50
        and rsi < 70
        and macd["bullish"]
        and macd["histogram_rising"]
        and acceleration > 0
    )

    return {
        "rsi": rsi,
        "macd": macd["macd"],
        "macd_signal": macd["signal"],
        "macd_histogram": macd["histogram"],
        "macd_bullish": macd["bullish"],
        "histogram_rising": macd["histogram_rising"],
        "momentum_acceleration": acceleration,
        "momentum_score": momentum_score,
        "momentum_bullish": momentum_bullish
    }


# ==========================================
# BREAKOUT DETECTOR V4.3
# ==========================================

def detect_breakout(candles, lookback=20):

    if len(candles) < lookback + 2:
        return None

    closed = candles[:-1]

    current = closed[-1]

    previous = closed[-(lookback + 1):-1]

    resistance = max(
        float(c[2]) for c in previous
    )

    close_price = float(current[4])

    if resistance <= 0:
        return None

    distance_pct = (
        (close_price / resistance) - 1
    ) * 100

    return {
        "breakout": close_price > resistance,
        "resistance": resistance,
        "distance_pct": distance_pct
    }


# ==========================================
# ANALISIS COIN
# ==========================================

def analyze_coin(symbol):

    candles = get_candles(symbol)

    if not candles:
        return None

    current = candles[-2]
    previous = candles[-3]

    # BREAKOUT
    breakout_data = detect_breakout(
        candles,
        BREAKOUT_LOOKBACK
    )

    if breakout_data is None:
        return None

    # MOMENTUM
    momentum = calculate_momentum(candles)

    if momentum is None:
        return None

    # BASELINE 24 CANDLE
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

    volume_now = float(current[7])
    volume_previous = float(previous[7])

    vol_now = volume_now / avg_volume_now

    vol_previous = (
        volume_previous / avg_volume_previous
    )

    trades_now = (
        int(current[8]) / avg_trades_now
    )

    trades_previous = (
        int(previous[8]) / avg_trades_previous
    )

    open_now = float(current[1])
    close_now = float(current[4])

    open_previous = float(previous[1])
    close_previous = float(previous[4])

    if open_now <= 0 or open_previous <= 0:
        return None

    change_now = (
        close_now / open_now - 1
    ) * 100

    change_previous = (
        close_previous / open_previous - 1
    ) * 100

    # ======================================
    # SKOR DASAR V4.2
    # ======================================

    base_score = 0

    if vol_now >= 1.5:
        base_score += 25

    elif vol_now >= 1.2:
        base_score += 15

    if vol_previous >= 1.2:
        base_score += 15

    if trades_now >= 1.3:
        base_score += 20

    elif trades_now >= 1.1:
        base_score += 10

    if trades_previous >= 1.1:
        base_score += 10

    if change_now > 0:
        base_score += 10

    if change_previous > 0:
        base_score += 10

    if close_now > close_previous:
        base_score += 10

    # ======================================
    # SKOR GABUNGAN V4.4
    # ======================================

    score = round(
        base_score * 0.70
        + momentum["momentum_score"]
    )

    score = min(100, score)

    # ======================================
    # KONFIRMASI DUA CANDLE
    # ======================================

    candle_confirmed = (
        vol_now >= 1.5
        and vol_previous >= 1.2
        and trades_now >= 1.3
        and trades_previous >= 1.1
        and change_now > 0
        and change_previous > 0
        and close_now > close_previous
    )

    # ======================================
    # STATUS
    # ======================================

    if avg_volume_now < MIN_AVG_VOLUME:

        status = "HINDARI - VOLUME RENDAH"

    elif (
        candle_confirmed
        and momentum["momentum_bullish"]
    ):

        status = "RADAR AWAL TERKONFIRMASI"

    elif score >= 40 and change_now > 0:

        status = "PANTAU"

    else:

        status = "BELUM ADA SINYAL"

    # ======================================
    # HASIL
    # ======================================

    return {
        "symbol": symbol,
        "price": close_now,
        "change": change_now,
        "previous_change": change_previous,

        "volume_ratio": vol_now,
        "previous_volume_ratio": vol_previous,

        "trade_ratio": trades_now,
        "previous_trade_ratio": trades_previous,

        "base_score": base_score,
        "score": score,
        "status": status,

        "candle_time": format_time(current[0]),

        # BREAKOUT
        "breakout": breakout_data["breakout"],
        "resistance": breakout_data["resistance"],
        "breakout_distance": breakout_data["distance_pct"],

        # MOMENTUM
        "rsi": momentum["rsi"],
        "macd": momentum["macd"],
        "macd_signal": momentum["macd_signal"],
        "macd_histogram": momentum["macd_histogram"],
        "macd_bullish": momentum["macd_bullish"],
        "histogram_rising": momentum["histogram_rising"],

        "momentum_acceleration": momentum["momentum_acceleration"],
        "momentum_score": momentum["momentum_score"],
        "momentum_bullish": momentum["momentum_bullish"]
    }


# ==========================================
# MESIN UTAMA V9
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
    print("Candle limit:", CANDLE_LIMIT)
    print("Konfirmasi: Dua candle selesai")
    print("Breakout: Resistance 20 candle")
    print("Momentum: RSI 14")
    print("Momentum: MACD 12/26/9")
    print("Momentum: Acceleration")
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
                "ANALYSIS ERROR:",
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

        print(
            "Skor dasar:",
            coin["base_score"],
            "/ 100"
        )

        print(
            "Skor momentum:",
            coin["momentum_score"],
            "/ 30"
        )

        print(
            "Skor gabungan:",
            coin["score"],
            "/ 100"
        )

        print("Status:", coin["status"])

        # BREAKOUT REPORT
        print(
            "Resistance:",
            coin["resistance"]
        )

        print(
            "Breakout:",
            "YA" if coin["breakout"] else "TIDAK"
        )

        print(
            "Jarak resistance:",
            round(coin["breakout_distance"], 2),
            "%"
        )

        # MOMENTUM REPORT
        print(
            "RSI 14:",
            round(coin["rsi"], 2)
        )

        print(
            "MACD:",
            coin["macd"]
        )

        print(
            "MACD Signal:",
            coin["macd_signal"]
        )

        print(
            "MACD Histogram:",
            coin["macd_histogram"]
        )

        print(
            "MACD Bullish:",
            "YA" if coin["macd_bullish"] else "TIDAK"
        )

        print(
            "Momentum Acceleration:",
            round(coin["momentum_acceleration"], 4),
            "%"
        )

        print(
            "Momentum Bullish:",
            "YA" if coin["momentum_bullish"] else "TIDAK"
        )

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

    breakout_coins = [
        c for c in results
        if c["breakout"]
    ]

    momentum_coins = [
        c for c in results
        if c["momentum_bullish"]
    ]

    print("\n========== RINGKASAN V9 V4.4 ==========")

    print("Total hasil:", len(results))
    print("Radar awal:", len(confirmed))
    print("Dalam pantauan:", len(watch))
    print("Breakout terdeteksi:", len(breakout_coins))
    print("Momentum bullish:", len(momentum_coins))

    if confirmed:

        print("\nKANDIDAT RADAR AWAL:")

        for coin in confirmed:

            print(
                coin["symbol"],
                "| Skor:",
                coin["score"],
                "| RSI:",
                round(coin["rsi"], 2)
            )

    else:

        print("\nBelum ada radar awal terkonfirmasi.")

    if breakout_coins:

        print("\nKOIN BREAKOUT:")

        for coin in breakout_coins:

            print(
                coin["symbol"],
                "| Resistance:",
                coin["resistance"]
            )

    if momentum_coins:

        print("\nKOIN MOMENTUM BULLISH:")

        for coin in momentum_coins:

            print(
                coin["symbol"],
                "| RSI:",
                round(coin["rsi"], 2),
                "| Momentum:",
                coin["momentum_score"]
            )

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
