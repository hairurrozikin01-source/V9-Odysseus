"""Odysseus read-only audit layer for V9 reports.

This first foundation is deterministic and explainable. It does not place orders,
connect to wallets/brokers, or require credentials. It audits an existing V9 JSON
report and produces risk flags for a human/operator to review.
"""
import json
import os
from datetime import datetime, timezone

VERSION = "ODYSSEUS-0.1.0"
DEFAULT_INPUT = "v9_scan_results.json"
DEFAULT_OUTPUT = "odysseus_audit_report.json"


def _finite_number(value):
    try:
        number = float(value)
        if number != number or abs(number) == float("inf"):
            return None
        return number
    except (TypeError, ValueError):
        return None


def audit_report(report):
    if not isinstance(report, dict):
        raise ValueError("V9 report must be a JSON object")
    results = report.get("results", [])
    failures = report.get("failures", [])
    if not isinstance(results, list) or not isinstance(failures, list):
        raise ValueError("V9 results and failures must be lists")

    flags = []
    audited = []
    mode = str(report.get("mode", "")).upper()
    if mode != "READ ONLY":
        flags.append({
            "severity": "CRITICAL",
            "code": "UNEXPECTED_EXECUTION_MODE",
            "message": "Mode laporan bukan READ ONLY; audit dihentikan untuk pemeriksaan manusia.",
        })

    failed_count = report.get("failed_count", len(failures))
    try:
        failed_count = int(failed_count)
    except (TypeError, ValueError):
        failed_count = len(failures)
    if failed_count:
        flags.append({
            "severity": "WARNING",
            "code": "ANALYSIS_FAILURES",
            "message": "Sebagian simbol gagal dianalisis; jangan anggap hasil pemindaian lengkap.",
            "count": failed_count,
        })

    for item in results:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "UNKNOWN"))
        score = _finite_number(item.get("score"))
        rsi = _finite_number(item.get("rsi_15m"))
        volume_ratio = _finite_number(item.get("volume_ratio_15m"))
        trend_30m = item.get("trend_30m_bullish") is True
        trend_1h = item.get("trend_1h_bullish") is True
        local_flags = []

        if score is None or score < 60:
            local_flags.append("SCORE_BELOW_MINIMUM")
        if rsi is not None and rsi >= 75:
            local_flags.append("RSI_OVERBOUGHT")
        if volume_ratio is None or volume_ratio < 1.5:
            local_flags.append("VOLUME_CONFIRMATION_WEAK")
        if not trend_30m or not trend_1h:
            local_flags.append("MULTI_TIMEFRAME_TREND_NOT_CONFIRMED")

        severity = "INFO"
        if "RSI_OVERBOUGHT" in local_flags:
            severity = "WARNING"
        if "MULTI_TIMEFRAME_TREND_NOT_CONFIRMED" in local_flags:
            severity = "WARNING"

        audited.append({
            "symbol": symbol,
            "score": score,
            "severity": severity,
            "risk_flags": local_flags,
            "human_review_required": bool(local_flags),
            "decision": "REVIEW" if local_flags else "MONITOR",
        })

    audited.sort(
        key=lambda item: (
            item["severity"] == "WARNING",
            len(item["risk_flags"]),
            item["score"] if item["score"] is not None else -1,
        ),
        reverse=True,
    )

    warning_count = sum(x["severity"] == "WARNING" for x in audited)
    review_count = sum(x["human_review_required"] for x in audited)
    recommendations = [
        "Gunakan hasil ini sebagai audit informasi, bukan instruksi transaksi.",
        "Periksa manual spread, likuiditas, berita, dan kondisi pasar sebelum mengambil keputusan.",
    ]
    if not audited:
        recommendations.insert(0, "Tidak ada sinyal V9 untuk diaudit pada pemindaian ini; tidak perlu memaksakan transaksi.")
    if warning_count:
        recommendations.insert(0, "Tinjau kandidat berstatus WARNING dan hindari mengejar harga yang sudah terlalu panas.")

    return {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ ONLY",
        "source_version": report.get("version"),
        "source_scan_time_utc": report.get("scan_time_utc"),
        "source_universe_count": report.get("universe_count"),
        "audited_signal_count": len(audited),
        "warning_count": warning_count,
        "review_count": review_count,
        "system_flags": flags,
        "signals": audited,
        "recommendations": recommendations,
        "safety": {
            "orders_enabled": False,
            "wallet_access": False,
            "broker_credentials_required": False,
            "automated_trade_instruction": False,
        },
    }


def run(input_file=DEFAULT_INPUT, output_file=DEFAULT_OUTPUT):
    with open(input_file, "r", encoding="utf-8") as handle:
        report = json.load(handle)
    audited = audit_report(report)
    temporary = output_file + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(audited, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output_file)
    print("Odysseus", VERSION, "| READ ONLY")
    print("Sinyal diaudit:", audited["audited_signal_count"])
    print("Peringatan:", audited["warning_count"])
    print("Perlu ditinjau:", audited["review_count"])
    print("Laporan:", output_file)
    print("Tidak ada order, wallet, atau akses broker.")
    return audited


if __name__ == "__main__":
    run()
