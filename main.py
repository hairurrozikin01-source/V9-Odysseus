
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# =========================================================
# V9 ODYSSEUS V4.5.3
# SIGNAL VALIDATION & PERFORMANCE INTELLIGENCE
# READ ONLY - NO AUTOMATIC TRADING
# CAPITAL PROTECTION FIRST
# =========================================================

VERSION = "V4.5.3"

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

HORIZONS = {
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
}


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
                    "User-Agent": "V9-Odysseus/4.5.3",
                    "Accept": "application/json",
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


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except (FileNotFoundError, json.JSONDecodeError):
        pass

    return []


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ema(values, period):
    if len(values) < period:
        return None

    alpha = 2 / (period + 1)
    result = sum(values[:period]) / period

    for value in values[period:]:
        result = alpha * value + (1 - alpha) * result

    return result


def calculate_rsi(closes, period=14):
    if len(closes) <= period:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_klines(symbol, interval, limit=CANDLE_LIMIT):
    return api_get(
        "/api/v3/klines",
        {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
    )


def candle_data(raw):
    return {
        "open_time": int(raw[0]),
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "close_time": int(raw[6]),
        "quote_volume": float(raw[7]),
        "trades": int(raw[8]),
    }


def get_universe():
    info = api_get("/api/v3/exchangeInfo")
    tickers = api_get("/api/v3/ticker/24hr")

    ticker_map = {
        item["symbol"]: item for item in tickers
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
            quote_volume = float(
                ticker.get("quoteVolume", 0)
            )
            last_price = float(
                ticker.get("lastPrice", 0)
            )
        except (ValueError, TypeError):
            continue

        if (
            quote_volume >= MIN_QUOTE_VOLUME_USDT
            and last_price > 0
        ):
            symbols.append({
                "symbol": symbol,
                "quote_volume_24h": quote_volume,
                "last_price": last_price,
            })

    symbols.sort(
        key=lambda x: x["quote_volume_24h"],
        reverse=True
    )

    if MAX_SYMBOLS > 0:
        symbols = symbols[:MAX_SYMBOLS]

    return symbols


def analyze_trend(symbol, interval):
    raw = get_klines(symbol, interval, 60)

    if len(raw) < 30:
        return False

    now_ms = int(time.time() * 1000)

    candles = [
        candle_data(x)
        for x in raw
        if int(x[6]) < now_ms
    ]

    if len(candles) < 30:
        return False

    closes = [x["close"] for x in candles]

    fast = ema(closes, 9)
    slow = ema(closes, 21)

    return (
        fast is not None
        and slow is not None
        and fast > slow
        and closes[-1] > fast
    )


def analyze_symbol(item):
    symbol = item["symbol"]

    raw = get_klines(symbol, SCAN_INTERVAL)

    now_ms = int(time.time() * 1000)

    candles = [
        candle_data(x)
        for x in raw
        if int(x[6]) < now_ms
    ]

    if len(candles) < 40:
        return None

    closes = [x["close"] for x in candles]
    current = candles[-1]
    previous = candles[-2]

    avg_volume = sum(
        x["quote_volume"] for x in candles[-21:-1]
    ) / 20

    volume_ratio = (
        current["quote_volume"] / avg_volume
        if avg_volume > 0 else 0
    )

    avg_trades = sum(
        x["trades"] for x in candles[-21:-1]
    ) / 20

    trade_ratio = (
        current["trades"] / avg_trades
        if avg_trades > 0 else 0
    )

    if avg_volume < MIN_AVG_QUOTE_VOLUME_15M:
        return None

    rsi = calculate_rsi(closes)

    fast = ema(closes, 9)
    slow = ema(closes, 21)

    if fast is None or slow is None:
        return None

    recent_high = max(
        x["high"]
        for x in candles[-BREAKOUT_LOOKBACK-1:-1]
    )

    bullish_30m = analyze_trend(
        symbol, VALIDATION_INTERVAL
    )

    bullish_1h = analyze_trend(
        symbol, TREND_INTERVAL
    )

    score = 0

    if fast > slow:
        score += 20

    if current["close"] > fast:
        score += 10

    if volume_ratio >= MIN_VOLUME_RATIO:
        score += 15

    if trade_ratio >= MIN_TRADE_RATIO:
        score += 10

    if 50 <= rsi <= 70:
        score += 10

    if current["close"] > recent_high:
        score += 20

    if bullish_30m:
        score += 10

    if bullish_1h:
        score += 5

    if rsi > 80 or rsi < 30:
        score = max(0, score - 15)

    # WAJIB: KEDUA TIMEFRAME HARUS BULLISH
    if not bullish_30m or not bullish_1h:
        return None

    if score < 60:
        return None

    if volume_ratio < MIN_VOLUME_RATIO:
        status = "PANTAU - VOLUME RENDAH"
    elif trade_ratio < MIN_TRADE_RATIO:
        status = "PANTAU - AKTIVITAS RENDAH"
    elif current["close"] <= previous["close"]:
        status = "PANTAU - MOMENTUM LEMAH"
    else:
        status = "RADAR AWAL - BULLISH TERKONFIRMASI"

    return {
        "symbol": symbol,
        "score": score,
        "price": current["close"],
        "direction": "BUY",
        "rsi_15m": round(rsi, 2),
        "volume_ratio_15m": round(volume_ratio, 2),
        "trade_ratio_15m": round(trade_ratio, 2),
        "trend_30m_bullish": bullish_30m,
        "trend_1h_bullish": bullish_1h,
        "quote_volume_24h": item["quote_volume_24h"],
        "status": status,
        "entry_time_ms": current["close_time"],
    }


def evaluate_history(history):
    now_ms = int(time.time() * 1000)

    for signal in history:
        for horizon, duration in HORIZONS.items():
            result = signal["validation"][horizon]

            if result["status"] != "PENDING":
                continue

            due_time = (
                signal["entry_time_ms"] + duration
            )

            if now_ms < due_time:
                continue

            try:
                raw = api_get(
                    "/api/v3/klines",
                    {
                        "symbol": signal["symbol"],
                        "interval": "15m",
                        "startTime": due_time - 900000,
                        "limit": 4,
                    }
                )

                eligible = [
                    candle_data(x)
                    for x in raw
                    if int(x[6]) >= due_time
                ]

                if not eligible:
                    continue

                exit_price = eligible[0]["close"]
                entry_price = signal["entry_price"]

                change = (
                    (exit_price - entry_price)
                    / entry_price
                ) * 100

                if abs(change) <= 0.10:
                    outcome = "NEUTRAL"
                elif (
                    signal["direction"] == "BUY"
                    and change > 0
                ):
                    outcome = "POSITIVE"
                else:
                    outcome = "NEGATIVE"

                result.update({
                    "status": outcome,
                    "exit_price": exit_price,
                    "change_pct": round(change, 4),
                    "evaluated_at": utc_now(),
                })

            except Exception as exc:
                result["last_error"] = str(exc)[:120]

            time.sleep(REQUEST_DELAY_SECONDS)

    return history


def update_history(results):
    history = load_history()
    history = evaluate_history(history)

    existing = {
        (x["symbol"], x["entry_time_ms"])
        for x in history
    }

    for item in results:
        key = (
            item["symbol"],
            item["entry_time_ms"]
        )

        if key in existing:
            continue

        history.append({
            "symbol": item["symbol"],
            "direction": item["direction"],
            "entry_price": item["price"],
            "entry_time_ms": item["entry_time_ms"],
            "created_at": utc_now(),
            "validation": {
                "30m": {"status": "PENDING"},
                "1h": {"status": "PENDING"},
            },
        })

    history = history[-5000:]

    save_json(HISTORY_FILE, history)

    return history


def calculate_performance(history):
    stats = {
        "total_completed": 0,
        "positive": 0,
        "negative": 0,
        "neutral": 0,
        "pending": 0,
        "success_rate_pct": None,
    }

    for signal in history:
        for result in signal["validation"].values():
            status = result["status"]

            if status == "PENDING":
                stats["pending"] += 1
            else:
                stats["total_completed"] += 1
                stats[status.lower()] += 1

    decided = stats["positive"] + stats["negative"]

    if decided > 0:
        stats["success_rate_pct"] = round(
            stats["positive"] / decided * 100, 2
        )

    return stats


def run_v9():
    print("=" * 55)
    print("V9 ODYSSEUS", VERSION)
    print("Mode: READ ONLY")
    print("Waktu:", utc_now())
    print("Scan: 15m | Validasi: 30m | Tren: 1h")
    print("=" * 55)

    universe = get_universe()

    print("Pasangan lolos filter:", len(universe))

    results = []
    failures = []

    for index, item in enumerate(universe, 1):
        try:
            result = analyze_symbol(item)

            if result:
                results.append(result)

        except Exception as exc:
            failures.append({
                "symbol": item["symbol"],
                "error": str(exc)[:150],
            })

        if index % 25 == 0 or index == len(universe):
            print(
                "Progres:", index, "/", len(universe),
                "| hasil:", len(results),
                "| gagal:", len(failures)
            )

        time.sleep(REQUEST_DELAY_SECONDS)

    results.sort(
        key=lambda x: (
            x["score"],
            x["quote_volume_24h"]
        ),
        reverse=True
    )

    history = update_history(results)
    performance = calculate_performance(history)

    report = {
        "version": VERSION,
        "scan_time_utc": utc_now(),
        "mode": "READ ONLY",
        "configuration": {
            "scan_interval": SCAN_INTERVAL,
            "validation_interval": VALIDATION_INTERVAL,
            "trend_interval": TREND_INTERVAL,
            "minimum_24h_volume_usdt": MIN_QUOTE_VOLUME_USDT,
            "minimum_average_15m_volume_usdt": MIN_AVG_QUOTE_VOLUME_15M,
        },
        "universe_count": len(universe),
        "analyzed_count": len(results),
        "failed_count": len(failures),
        "performance": performance,
        "results": results,
        "failures": failures,
    }

    save_json(OUTPUT_FILE, report)

    print("\n========== TOP 20 V9 ==========")

    for row in results[:20]:
        print(
            row["symbol"],
            "| skor:", row["score"],
            "| RSI:", row["rsi_15m"],
            "| volume:", row["volume_ratio_15m"],
            "| trades:", row["trade_ratio_15m"],
            "| 30m:", row["trend_30m_bullish"],
            "| 1h:", row["trend_1h_bullish"],
            "|", row["status"],
        )

    print("\n========== STATISTIK ==========")

    for key, value in performance.items():
        print(key + ":", value)

    print("Gagal dianalisis:", len(failures))
    print("Laporan:", OUTPUT_FILE)
    print("Riwayat:", HISTORY_FILE)
    print("READ ONLY - TIDAK ADA TRANSAKSI")


if __name__ == "__main__":
    try:
        run_v9()
    except Exception as exc:
        print("FATAL ERROR:", repr(exc))
        raise
