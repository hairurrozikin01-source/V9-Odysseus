"""SHIB Hunter: read-only multi-chain early-token radar.

Discovery is seeded by DexScreener latest token profiles and boosts. This is
not an exhaustive scan of every token or every chain, and it is not a security
audit. Candidates are watchlist items only; no wallet or trading actions exist.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VERSION = "SHIB-HUNTER-0.1.0"
BASE_URL = "https://api.dexscreener.com"
USER_AGENT = "V9-Odysseus-SHIB-Hunter/0.1.0"

# Balanced screening: reject thin or extremely overheated pools before scoring.
MIN_LIQUIDITY_USD = 25_000
MIN_VOLUME_24H_USD = 10_000
MIN_TXNS_24H = 30
MAX_POOL_AGE_HOURS = 72
MAX_CHANGE_1H_PCT = 100
MAX_CHANGE_24H_PCT = 300
MAX_CANDIDATES_TO_ENRICH = 40
REQUEST_DELAY_SECONDS = 0.25
OUTPUT_FILE = "shib_hunter_results.json"


def api_get(path):
    request = urllib.request.Request(
        BASE_URL + path,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_tokens():
    """Return unique chain/address seeds from public discovery endpoints."""
    found = {}
    for endpoint in (
        "/token-profiles/latest/v1",
        "/token-boosts/latest/v1",
    ):
        payload = api_get(endpoint)
        if not isinstance(payload, list):
            continue
        for item in payload:
            chain = str(item.get("chainId") or "").strip().lower()
            address = str(item.get("tokenAddress") or "").strip()
            if chain and address:
                found[(chain, address)] = {
                    "chain_id": chain,
                    "token_address": address,
                    "discovery_sources": sorted(set(
                        found.get((chain, address), {}).get("discovery_sources", [])
                        + [endpoint.rsplit("/", 1)[-1]]
                    )),
                }
    return list(found.values())


def _number(value):
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _pair_metrics(pair, token_address, now_ms=None):
    base = pair.get("baseToken") or {}
    quote = pair.get("quoteToken") or {}
    token = base if str(base.get("address", "")).lower() == token_address.lower() else quote
    liquidity = _number((pair.get("liquidity") or {}).get("usd"))
    volume = pair.get("volume") or {}
    txns = pair.get("txns") or {}
    changes = pair.get("priceChange") or {}
    h24 = txns.get("h24") or {}
    h1_volume = _number(volume.get("h1")) or 0.0
    h24_volume = _number(volume.get("h24")) or 0.0
    buys = int(_number(h24.get("buys")) or 0)
    sells = int(_number(h24.get("sells")) or 0)
    created = _number(pair.get("pairCreatedAt"))
    now_ms = now_ms or int(time.time() * 1000)
    age_hours = max(0.0, (now_ms - created) / 3_600_000) if created else None
    return {
        "name": token.get("name") or "Unknown",
        "symbol": token.get("symbol") or "UNKNOWN",
        "price_usd": _number(pair.get("priceUsd")),
        "liquidity_usd": liquidity,
        "volume_1h_usd": h1_volume,
        "volume_24h_usd": h24_volume,
        "buys_24h": buys,
        "sells_24h": sells,
        "transactions_24h": buys + sells,
        "price_change_1h_pct": _number(changes.get("h1")),
        "price_change_24h_pct": _number(changes.get("h24")),
        "fdv_usd": _number(pair.get("fdv")),
        "market_cap_usd": _number(pair.get("marketCap")),
        "pool_age_hours": round(age_hours, 2) if age_hours is not None else None,
        "pair_address": pair.get("pairAddress"),
        "dex_id": pair.get("dexId"),
        "pair_url": pair.get("url"),
    }


def score_candidate(metrics):
    """Return (score, rejection reasons); score is a ranking aid, not a forecast."""
    rejected = []
    liquidity = metrics["liquidity_usd"]
    volume = metrics["volume_24h_usd"]
    txns = metrics["transactions_24h"]
    age = metrics["pool_age_hours"]
    change_1h = metrics["price_change_1h_pct"]
    change_24h = metrics["price_change_24h_pct"]

    if metrics["price_usd"] is None or metrics["price_usd"] <= 0:
        rejected.append("missing_or_invalid_price")
    if liquidity is None or liquidity < MIN_LIQUIDITY_USD:
        rejected.append("liquidity_below_balanced_floor")
    if volume < MIN_VOLUME_24H_USD:
        rejected.append("volume_below_balanced_floor")
    if txns < MIN_TXNS_24H:
        rejected.append("insufficient_24h_transactions")
    if age is None or age > MAX_POOL_AGE_HOURS:
        rejected.append("pool_age_outside_early_window")
    if (change_1h is not None and change_1h > MAX_CHANGE_1H_PCT) or (
        change_24h is not None and change_24h > MAX_CHANGE_24H_PCT
    ):
        rejected.append("overheated_pump_protection")
    if metrics["sells_24h"] > metrics["buys_24h"] * 1.5:
        rejected.append("sell_pressure_high")

    if rejected:
        return 0, rejected

    score = 0
    # Liquidity depth: 0-25 points.
    score += 25 if liquidity >= 250_000 else 18 if liquidity >= 100_000 else 12
    # Turnover relative to liquidity: 0-20 points.
    turnover = volume / liquidity if liquidity else 0
    score += 20 if 0.5 <= turnover <= 5 else 12 if 0.2 <= turnover < 0.5 else 5
    # Buyer participation: 0-20 points.
    total = metrics["buys_24h"] + metrics["sells_24h"]
    buy_share = metrics["buys_24h"] / total if total else 0
    score += 20 if buy_share >= 0.65 else 12 if buy_share >= 0.55 else 5
    # Early pool age: 0-15 points.
    score += 15 if age <= 12 else 10 if age <= 36 else 5
    # Modest positive momentum: 0-20 points; avoid extreme spikes.
    if change_1h is not None and 0 <= change_1h <= 25:
        score += 10
    elif change_1h is not None and -5 <= change_1h < 0:
        score += 4
    if change_24h is not None and 0 <= change_24h <= 60:
        score += 10
    elif change_24h is not None and -10 <= change_24h < 0:
        score += 4
    return min(score, 100), []


def enrich_candidate(seed):
    path = "/token-pairs/v1/{}/{}".format(
        urllib.parse.quote(seed["chain_id"], safe=""),
        urllib.parse.quote(seed["token_address"], safe=""),
    )
    pairs = api_get(path)
    if not isinstance(pairs, list) or not pairs:
        return None
    metrics_list = [
        _pair_metrics(pair, seed["token_address"])
        for pair in pairs
        if isinstance(pair, dict)
    ]
    metrics_list.sort(
        key=lambda x: x["liquidity_usd"] or 0,
        reverse=True,
    )
    best = metrics_list[0]
    score, rejected = score_candidate(best)
    return {
        **seed,
        **best,
        "score": score,
        "decision": "WATCHLIST" if not rejected and score >= 55 else "REJECTED",
        "rejection_reasons": rejected or (
            ["score_below_watchlist_threshold"] if score < 55 else []
        ),
        "security_status": "NOT_VERIFIED",
        "trading_status": "READ_ONLY_NO_ORDERS",
    }


def save_report(report, filename=OUTPUT_FILE):
    temporary = filename + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, filename)


def run():
    seeds = discover_tokens()
    candidates = []
    failures = []
    for seed in seeds[:MAX_CANDIDATES_TO_ENRICH]:
        try:
            item = enrich_candidate(seed)
            if item:
                candidates.append(item)
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            failures.append({
                "chain_id": seed["chain_id"],
                "token_address": seed["token_address"],
                "error": str(exc)[:160],
            })
        time.sleep(REQUEST_DELAY_SECONDS)

    candidates.sort(
        key=lambda item: (item["decision"] == "WATCHLIST", item["score"]),
        reverse=True,
    )
    report = {
        "version": VERSION,
        "scan_time_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ ONLY",
        "risk_profile": "BALANCED",
        "coverage": (
            "Multi-chain discovery seeds from DexScreener token profiles and boosts; "
            "not an exhaustive scan of every token or every supported chain."
        ),
        "security_notice": (
            "Token safety, honeypot status, ownership, taxes, and holder concentration "
            "are not verified by this radar. Manual/on-chain due diligence is required."
        ),
        "discovered_seed_count": len(seeds),
        "enriched_count": len(candidates),
        "watchlist_count": sum(x["decision"] == "WATCHLIST" for x in candidates),
        "failure_count": len(failures),
        "candidates": candidates,
        "failures": failures,
    }
    save_report(report)
    print("SHIB Hunter", VERSION, "| READ ONLY | BALANCED")
    print("Seeds:", len(seeds), "| enriched:", len(candidates))
    print("Watchlist:", report["watchlist_count"], "| failures:", len(failures))
    print("Report:", OUTPUT_FILE)
    print("No wallet connection. No purchases. No orders.")
    return report


if __name__ == "__main__":
    run()
