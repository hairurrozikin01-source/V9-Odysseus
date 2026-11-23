
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ============================================================
# V9 ODYSSEUS V4.5.1 - BALANCED EARLY DETECTION
# READ ONLY: no order placement, no wallet signing, no API keys.
# ============================================================
VERSION = "V4.5.1"
PRIMARY_INTERVAL = "15m"
CONFIRM_INTERVAL = "1h"
CANDLE_LIMIT = 100
MIN_QUOTE_VOLUME_USDT = 5_000_000       # 24h quote volume filter
MIN_AVG_QUOTE_VOLUME_15M = 50_000       # average quote volume per 15m candle
MAX_SYMBOLS = 0                         # 0 = all symbols passing liquidity filter
REQUEST_DELAY_SECONDS = 0.08
BREAKOUT_LOOKBACK = 20
OUTPUT_FILE = "v9_scan_results.json"

BASE_URLS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
]


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def api_get(path, params=None):
    query = urllib.parse.urlencode(params or {})
    errors = []
    for base in BASE_URLS:
        url = base + path + ("?" + query if query else "")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "V9-Odysseus/4.5.1", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            errors.append("HTTP " + str(exc.code))
            if exc.code == 429 or exc.code == 418:
                time.sleep(3)
        except Exception as exc:
            errors.append(str(exc)[:100])
    raise RuntimeError("Binance API gagal: " + " | ".join(errors[-3:]))


def get_universe():
    info = api_get("/api/v3/exchangeInfo")
    tickers = api_get("/api/v3/ticker/24hr")
    ticker_map = {item["symbol"]: item for item in tickers}
    symbols = []
    for item in info.get("symbols", []):
        symbol = item.get("symbol", "")
        if (item.get("status") != "TRADING"
                or item.get("quoteAsset") != "USDT"
                or item.get("isSpotTradingAllowed") is False):
            continue
        ticker = ticker_map.get(symbol)
        if not ticker:
            continue
        try:
            quote_volume = float(ticker.get("quoteVolume", 0))
            last_price = float(ticker.get("lastPrice", 0))
        except (TypeError, ValueError):
            continue
        if quote_volume >= MIN_QUOTE_VOLUME_USDT and last_price > 0:
            symbols.append({
                "symbol": symbol,
                "quote_volume_24h": quote_volume,
                "last_price": last_price,
            })
    symbols.sort(key=lambda row: row["quote_volume_24h"], reverse=True)
    if MAX_SYMBOLS > 0:
        symbols = symbols[:MAX_SYMBOLS]
    return symbols


def candles(symbol, interval):
    rows = api_get("/api/v3/klines", {
        "symbol": symbol,
        "interval": interval,
        "limit": CANDLE_LIMIT,
    })
    if not isinstance(rows, list) or len(rows) < 60:
        raise ValueError("Candle tidak cukup")
    return rows[:-1]  # ignore currently-forming candle


def ema(values, period):
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = item * alpha + value * (1 - alpha)
    return value


def rsi(values, period=14):
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def analyze(symbol_row):
    symbol = symbol_row["symbol"]
    c15 = candles(symbol, PRIMARY_INTERVAL)
    time.sleep(REQUEST_DELAY_SECONDS)
    c1h = candles(symbol, CONFIRM_INTERVAL)

    closes = [float(c[4]) for c in c15]
    highs = [float(c[2]) for c in c15]
    quote_volumes = [float(c[7]) for c in c15]
    trades = [float(c[8]) for c in c15]
    if len(closes) < 55:
        return None

    last_close = closes[-1]
    previous_close = closes[-2]
    avg_quote_volume = sum(quote_volumes[-25:-1]) / 24
    avg_trades = sum(trades[-25:-1]) / 24
    volume_ratio = quote_volumes[-1] / avg_quote_volume if avg_quote_volume else 0
    trade_ratio = trades[-1] / avg_trades if avg_trades else 0
    candle_change = ((last_close / float(c15[-1][1])) - 1) * 100 if float(c15[-1][1]) else 0
    previous_change = ((previous_close / float(c15[-2][1])) - 1) * 100 if float(c15[-2][1]) else 0

    resistance = max(highs[-(BREAKOUT_LOOKBACK + 1):-1])
    breakout = last_close > resistance
    distance_to_resistance = ((last_close / resistance) - 1) * 100 if resistance else 0
    rsi_value = rsi(closes)

    h1_closes = [float(c[4]) for c in c1h]
    ema20 = ema(h1_closes, 20)
    ema50 = ema(h1_closes, 50)
    h1_bullish = bool(ema20 and ema50 and h1_closes[-1] > ema20 > ema50)

    score = 0
    if volume_ratio >= 2.0:
        score += 25
    elif volume_ratio >= 1.5:
        score += 20
    elif volume_ratio >= 1.2:
        score += 10
    if trade_ratio >= 1.5:
        score += 20
    elif trade_ratio >= 1.3:
        score += 15
    elif trade_ratio >= 1.1:
        score += 8
    if candle_change > 0:
        score += 10
    if previous_change > 0:
        score += 5
    if last_close > previous_close:
        score += 5
    if h1_bullish:
        score += 20
    if rsi_value is not None and 50 <= rsi_value <= 72:
        score += 10
    if breakout:
        score += 10
    score = min(score, 100)

    enough_liquidity = avg_quote_volume >= MIN_AVG_QUOTE_VOLUME_15M
    early_setup = (
        enough_liquidity and volume_ratio >= 1.5 and trade_ratio >= 1.3
        and candle_change > 0 and h1_bullish
        and rsi_value is not None and 50 <= rsi_value <= 75
    )
    if not enough_liquidity:
        status = "HINDARI - LIKUIDITAS RENDAH"
    elif early_setup and breakout:
        status = "BREAKOUT TERKONFIRMASI"
    elif early_setup:
        status = "RADAR AWAL - TERKONFIRMASI 1H"
    elif score >= 45:
        status = "PANTAU"
    else:
        status = "BELUM ADA SINYAL"

    return {
        "symbol": symbol,
        "price": last_close,
        "quote_volume_24h_usdt": round(symbol_row["quote_volume_24h"], 2),
        "avg_quote_volume_15m_usdt": round(avg_quote_volume, 2),
        "volume_ratio_15m": round(volume_ratio, 2),
        "trade_ratio_15m": round(trade_ratio, 2),
        "change_15m_pct": round(candle_change, 3),
        "rsi_15m": round(rsi_value, 2) if rsi_value is not None else None,
        "trend_1h_bullish": h1_bullish,
        "breakout_20_candles": breakout,
        "resistance_20_candles": resistance,
        "distance_to_resistance_pct": round(distance_to_resistance, 3),
        "score": score,
        "status": status,
        "candle_close_time_utc": datetime.fromtimestamp(int(c15[-1][6]) / 1000, timezone.utc).isoformat(),
    }


def run_v9():
    print("=" * 58)
    print("V9 ODYSSEUS", VERSION, "| BALANCED EARLY DETECTION")
    print("Waktu:", utc_now())
    print("Mode: READ ONLY | 15m scan | 1h trend confirmation")
    print("Minimum 24h quote volume:", f"${MIN_QUOTE_VOLUME_USDT:,.0f}")
    print("=" * 58)

    universe = get_universe()
    print("Pasangan USDT lolos filter likuiditas:", len(universe))
    results = []
    failures = []
    for index, item in enumerate(universe, start=1):
        try:
            result = analyze(item)
            if result:
                results.append(result)
        except Exception as exc:
            failures.append({"symbol": item["symbol"], "error": str(exc)[:160]})
        if index % 25 == 0:
            print(f"Progres: {index}/{len(universe)} | hasil: {len(results)} | gagal: {len(failures)}")
        time.sleep(REQUEST_DELAY_SECONDS)

    results.sort(key=lambda row: (row["score"], row["quote_volume_24h_usdt"]), reverse=True)
    report = {
        "version": VERSION,
        "scan_time_utc": utc_now(),
        "mode": "READ ONLY",
        "configuration": {
            "scan_interval": PRIMARY_INTERVAL,
            "confirmation_interval": CONFIRM_INTERVAL,
            "min_quote_volume_24h_usdt": MIN_QUOTE_VOLUME_USDT,
            "min_avg_quote_volume_15m_usdt": MIN_AVG_QUOTE_VOLUME_15M,
            "max_symbols": MAX_SYMBOLS,
        },
        "universe_count": len(universe),
        "analyzed_count": len(results),
        "failed_count": len(failures),
        "results": results,
        "failures": failures,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print("\n========== TOP 20 HASIL V9 ==========")
    for row in results[:20]:
        print(
            row["symbol"], "| skor", row["score"],
            "| volume", row["volume_ratio_15m"], "x",
            "| trades", row["trade_ratio_15m"], "x",
            "| RSI", row["rsi_15m"],
            "| 1h bullish", row["trend_1h_bullish"],
            "|", row["status"],
        )
    print("\nRadar awal:", sum(1 for row in results if row["status"] == "RADAR AWAL - TERKONFIRMASI 1H"))
    print("Breakout:", sum(1 for row in results if row["status"] == "BREAKOUT TERKONFIRMASI"))
    print("Dalam pantauan:", sum(1 for row in results if row["status"] == "PANTAU"))
    print("Gagal dianalisis:", len(failures))
    print("Laporan tersimpan:", OUTPUT_FILE)
    print("READ ONLY - TIDAK ADA TRANSAKSI YANG DILAKUKAN")


if __name__ == "__main__":
    try:
        run_v9()
    except Exception as exc:
        print("FATAL ERROR:", repr(exc))
        raise
