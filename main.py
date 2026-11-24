
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ============================================================
# V9 ODYSSEUS V4.5.2 - SIGNAL INTELLIGENCE
# READ ONLY - NO AUTOMATIC TRADING
# Capital Protection First
# ============================================================

VERSION = "V4.5.2"

SCAN_INTERVAL = "15m"
VALIDATION_INTERVAL = "30m"
TREND_INTERVAL = "1h"

CANDLE_LIMIT = 100
BREAKOUT_LOOKBACK = 20

MIN_QUOTE_VOLUME_USDT = 5_000_000
MIN_AVG_QUOTE_VOLUME_15M = 50_000

MIN_VOLUME_RATIO = 1.5
MIN_TRADE_RATIO = 1.3

REQUEST_DELAY_SECONDS = 0.12
MAX_SYMBOLS = 0

OUTPUT_FILE = "v9_scan_results.json"
HISTORY_FILE = "v9_signal_history.json"

BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
]


def utc_now():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def api_get(path, params=None):
    query = urllib.parse.urlencode(params or {})
    errors = []

    for base in BASE_URLS:
        url = base + path
        if query:
            url += "?" + query

        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "V9-Odysseus/4.5.2",
                    "Accept": "application/json"
                }
            )

            with urllib.request.urlopen(
                request, timeout=20
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as exc:
            errors.append("HTTP " + str(exc.code))
            if exc.code in (418, 429):
                time.sleep(5)

        except Exception as exc:
            errors.append(str(exc)[:100])

    raise RuntimeError(
        "Binance API gagal: " + " | ".join(errors[-3:])
    )


def ema(values, period):
    if len(values) < period:
        return None

    alpha = 2 / (period + 1)
    result = sum(values[:period]) / period

    for value in values[period:]:
        result = value * alpha + result * (1 - alpha)

    return result


def calculate_rsi(values, period=14):
    if len(values) <= period:
        return None

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(x, 0) for x in changes]
    losses = [max(-x, 0) for x in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_universe():
    info = api_get("/api/v3/exchangeInfo")
    tickers = api_get("/api/v3/ticker/24hr")

    ticker_map = {
        item["symbol"]: item
        for item in tickers
    }

    symbols = []

    for item in info.get("symbols", []):
        symbol = item.get("symbol", "")

        if (
            item.get("status") != "TRADING"
            or item.get("quoteAsset") != "USDT"
            or item.get("isSpotTradingAllowed") is False
        ):
            continue

        ticker = ticker_map.get(symbol)

        if not ticker:
            continue

        try:
            volume = float(ticker.get("quoteVolume", 0))
            price = float(ticker.get("lastPrice", 0))
        except (TypeError, ValueError):
            continue

        if volume >= MIN_QUOTE_VOLUME_USDT and price > 0:
            symbols.append({
                "symbol": symbol,
                "quote_volume_24h": volume,
                "last_price": price
            })

    symbols.sort(
        key=lambda x: x["quote_volume_24h"],
        reverse=True
    )

    if MAX_SYMBOLS > 0:
        symbols = symbols[:MAX_SYMBOLS]

    return symbols


def get_candles(symbol, interval):
    rows = api_get(
        "/api/v3/klines",
        {
            "symbol": symbol,
            "interval": interval,
            "limit": CANDLE_LIMIT
        }
    )

    if not isinstance(rows, list) or len(rows) < 60:
        raise ValueError("Data candle tidak cukup")

    # Candle terakhir belum selesai, jangan digunakan.
    return rows[:-1]


def analyze(symbol_data):
    symbol = symbol_data["symbol"]

    c15 = get_candles(symbol, SCAN_INTERVAL)
    time.sleep(REQUEST_DELAY_SECONDS)

    c30 = get_candles(symbol, VALIDATION_INTERVAL)
    time.sleep(REQUEST_DELAY_SECONDS)

    c1h = get_candles(symbol, TREND_INTERVAL)

    closes15 = [float(c[4]) for c in c15]
    opens15 = [float(c[1]) for c in c15]
    highs15 = [float(c[2]) for c in c15]
    lows15 = [float(c[3]) for c in c15]
    volumes15 = [float(c[7]) for c in c15]
    trades15 = [float(c[8]) for c in c15]

    closes30 = [float(c[4]) for c in c30]
    closes1h = [float(c[4]) for c in c1h]

    close_price = closes15[-1]
    candle_open = opens15[-1]
    candle_high = highs15[-1]
    candle_low = lows15[-1]

    change15 = (
        (close_price / candle_open - 1) * 100
        if candle_open else 0
    )

    avg_volume = sum(volumes15[-25:-1]) / 24
    avg_trades = sum(trades15[-25:-1]) / 24

    volume_ratio = (
        volumes15[-1] / avg_volume
        if avg_volume else 0
    )

    trade_ratio = (
        trades15[-1] / avg_trades
        if avg_trades else 0
    )

    rsi_value = calculate_rsi(closes15)

    ema20_30 = ema(closes30, 20)
    ema50_30 = ema(closes30, 50)

    ema20_1h = ema(closes1h, 20)
    ema50_1h = ema(closes1h, 50)

    bullish30 = bool(
        ema20_30
        and ema50_30
        and closes30[-1] > ema20_30 > ema50_30
    )

    bullish1h = bool(
        ema20_1h
        and ema50_1h
        and closes1h[-1] > ema20_1h > ema50_1h
    )

    resistance = max(
        highs15[-(BREAKOUT_LOOKBACK + 1):-1]
    )

    breakout = close_price > resistance

    # False breakout:
    # Harga sempat menembus resistance tetapi
    # candle berakhir kembali di bawah resistance.
    false_breakout = (
        candle_high > resistance
        and close_price <= resistance
    )

    candle_range = max(candle_high - candle_low, 0)
    upper_wick = candle_high - max(
        candle_open, close_price
    )

    upper_wick_ratio = (
        upper_wick / candle_range
        if candle_range > 0 else 0
    )

    if (
        candle_high > resistance
        and close_price <= resistance
        and upper_wick_ratio >= 0.35
    ):
        false_breakout = True

    liquidity_ok = (
        avg_volume >= MIN_AVG_QUOTE_VOLUME_15M
    )

    score = 0

    if volume_ratio >= 2:
        score += 25
    elif volume_ratio >= 1.5:
        score += 20
    elif volume_ratio >= 1.2:
        score += 10

    if trade_ratio >= 1.5:
        score += 15
    elif trade_ratio >= 1.3:
        score += 12
    elif trade_ratio >= 1.1:
        score += 5

    if change15 > 0:
        score += 5

    if bullish30:
        score += 15

    if bullish1h:
        score += 20

    if rsi_value is not None and 50 <= rsi_value <= 70:
        score += 10

    if breakout:
        score += 10

    if not liquidity_ok:
        status = "HINDARI - LIKUIDITAS RENDAH"

    elif false_breakout:
        status = "HINDARI - FALSE BREAKOUT"

    elif breakout and bullish30 and bullish1h:
        if volume_ratio >= MIN_VOLUME_RATIO:
            status = "BREAKOUT TERKONFIRMASI"
        else:
            status = "PANTAU - VOLUME BELUM KUAT"

    elif (
        bullish30
        and bullish1h
        and volume_ratio >= MIN_VOLUME_RATIO
        and trade_ratio >= MIN_TRADE_RATIO
        and rsi_value is not None
        and 50 <= rsi_value <= 72
        and change15 > 0
    ):
        status = "RADAR AWAL - KONFIRMASI 30M/1H"

    elif score >= 45:
        status = "PANTAU"

    else:
        status = "BELUM ADA SINYAL"

    candle_time = int(c15[-1][6])

    return {
        "symbol": symbol,
        "price": close_price,
        "score": score,
        "status": status,
        "volume_ratio_15m": round(volume_ratio, 2),
        "trade_ratio_15m": round(trade_ratio, 2),
        "change_15m_pct": round(change15, 3),
        "rsi_15m": (
            round(rsi_value, 2)
            if rsi_value is not None else None
        ),
        "trend_30m_bullish": bullish30,
        "trend_1h_bullish": bullish1h,
        "breakout": breakout,
        "false_breakout": false_breakout,
        "upper_wick_ratio": round(upper_wick_ratio, 3),
        "resistance": resistance,
        "quote_volume_24h_usdt": round(
            symbol_data["quote_volume_24h"], 2
        ),
        "avg_quote_volume_15m": round(avg_volume, 2),
        "candle_close_time_ms": candle_time
    }


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except (FileNotFoundError, json.JSONDecodeError):
        pass

    return []


def update_history(results):
    history = load_history()

    # Evaluasi sinyal lama setelah 4 candle 15m.
    prices = {
        row["symbol"]: row
        for row in results
    }

    for item in history:
        if item.get("status") != "PENDING":
            continue

        current = prices.get(item["symbol"])

        if not current:
            continue

        if (
            current["candle_close_time_ms"]
            < item["evaluation_time_ms"]
        ):
            continue

        entry = item["entry_price"]
        exit_price = current["price"]

        if entry <= 0:
            continue

        change = (exit_price / entry - 1) * 100

        item["exit_price"] = exit_price
        item["return_pct"] = round(change, 4)
        item["result"] = (
            "POSITIVE" if change > 0
            else "NEGATIVE" if change < 0
            else "FLAT"
        )
        item["status"] = "COMPLETED"

    # Catat sinyal baru tanpa menggandakan candle.
    existing = {
        (
            item["symbol"],
            item["signal_candle_time_ms"]
        )
        for item in history
    }

    for row in results:
        if row["status"] not in (
            "RADAR AWAL - KONFIRMASI 30M/1H",
            "BREAKOUT TERKONFIRMASI"
        ):
            continue

        key = (
            row["symbol"],
            row["candle_close_time_ms"]
        )

        if key in existing:
            continue

        history.append({
            "symbol": row["symbol"],
            "signal_time_utc": utc_now(),
            "signal_candle_time_ms": row["candle_close_time_ms"],
            "evaluation_time_ms": (
                row["candle_close_time_ms"] + 4 * 15 * 60 * 1000
            ),
            "entry_price": row["price"],
            "score": row["score"],
            "signal_type": row["status"],
            "status": "PENDING"
        })

    history = history[-500:]

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    completed = [
        item for item in history
        if item.get("status") == "COMPLETED"
    ]

    positive = sum(
        1 for item in completed
        if item.get("result") == "POSITIVE"
    )

    negative = sum(
        1 for item in completed
        if item.get("result") == "NEGATIVE"
    )

    total = positive + negative

    observed_rate = (
        round(positive / total * 100, 2)
        if total else None
    )

    return {
        "total_completed": len(completed),
        "positive": positive,
        "negative": negative,
        "pending": sum(
            1 for item in history
            if item.get("status") == "PENDING"
        ),
        "observed_positive_rate_pct": observed_rate
    }


def run_v9():
    print("=" * 60)
    print("V9 ODYSSEUS", VERSION, "| SIGNAL INTELLIGENCE")
    print("Waktu:", utc_now())
    print("Mode: READ ONLY")
    print("Scan: 15m | Validasi: 30m | Tren: 1h")
    print("Minimum volume 24h: $5,000,000")
    print("=" * 60)

    universe = get_universe()

    print(
        "Pasangan USDT lolos filter:",
        len(universe)
    )

    results = []
    failures = []

    for index, item in enumerate(universe, 1):
        try:
            result = analyze(item)

            if result:
                results.append(result)

        except Exception as exc:
            failures.append({
                "symbol": item["symbol"],
                "error": str(exc)[:150]
            })

        if index % 25 == 0 or index == len(universe):
            print(
                "Progres:",
                index, "/", len(universe),
                "| hasil:", len(results),
                "| gagal:", len(failures)
            )

        time.sleep(REQUEST_DELAY_SECONDS)

    results.sort(
        key=lambda x: (
            x["score"],
            x["quote_volume_24h_usdt"]
        ),
        reverse=True
    )

    performance = update_history(results)

    report = {
        "version": VERSION,
        "scan_time_utc": utc_now(),
        "mode": "READ ONLY",
        "configuration": {
            "scan_interval": SCAN_INTERVAL,
            "validation_interval": VALIDATION_INTERVAL,
            "trend_interval": TREND_INTERVAL,
            "minimum_24h_volume_usdt": MIN_QUOTE_VOLUME_USDT,
            "minimum_average_15m_volume_usdt": MIN_AVG_QUOTE_VOLUME_15M
        },
        "universe_count": len(universe),
        "analyzed_count": len(results),
        "failed_count": len(failures),
        "performance": performance,
        "results": results,
        "failures": failures
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n========== TOP 20 V9 ==========")

    for row in results[:20]:
        print(
            row["symbol"],
            "| skor:", row["score"],
            "| volume:", row["volume_ratio_15m"], "x",
            "| trades:", row["trade_ratio_15m"], "x",
            "| RSI:", row["rsi_15m"],
            "| 30m:", row["trend_30m_bullish"],
            "| 1h:", row["trend_1h_bullish"],
            "|", row["status"]
        )

    print("\n========== STATISTIK ==========")

    for key, value in performance.items():
        print(key + ":", value)

    print("\nGagal dianalisis:", len(failures))
    print("Laporan:", OUTPUT_FILE)
    print("Riwayat:", HISTORY_FILE)
    print("READ ONLY - TIDAK ADA TRANSAKSI")


if __name__ == "__main__":
    try:
        run_v9()
    except Exception as exc:
        print("FATAL ERROR:", repr(exc))
        raise
                
