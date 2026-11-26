"""Odysseus read-only audit layer with fail-closed data validation."""
import json
import math
import os
from datetime import datetime, timezone

VERSION = "ODYSSEUS-0.2.0"
DEFAULT_INPUT = "v9_scan_results.json"
DEFAULT_OUTPUT = "odysseus_audit_report.json"


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def audit_report(report):
    if not isinstance(report, dict):
        raise ValueError("V9 report must be a JSON object")

    results = report.get("results")
    failures = report.get("failures", [])
    if not isinstance(results, list) or not isinstance(failures, list):
        raise ValueError("V9 results and failures must be lists")

    system_flags = []
    audited = []
    mode = str(report.get("mode", "")).upper()
    if mode != "READ ONLY":
        system_flags.append({
            "severity": "CRITICAL",
            "code": "UNEXPECTED_EXECUTION_MODE",
            "message": "Mode bukan READ ONLY; audit diblokir.",
        })

    declared_failures = report.get("failed_count", len(failures))
    try:
        declared_failures = int(declared_failures)
    except (TypeError, ValueError):
        declared_failures = -1
    if declared_failures < 0 or declared_failures != len(failures):
        system_flags.append({
            "severity": "WARNING",
            "code": "FAILURE_COUNT_MISMATCH",
            "message": "Jumlah kegagalan laporan tidak konsisten dengan daftar failures.",
            "listed_failures": len(failures),
            "declared_failures": report.get("failed_count"),
        })
    if failures:
        system_flags.append({
            "severity": "WARNING",
            "code": "ANALYSIS_FAILURES",
            "message": "Sebagian simbol gagal dianalisis; hasil pemindaian tidak lengkap.",
            "count": len(failures),
        })

    seen_symbols = set()
    invalid_rows = 0
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            invalid_rows += 1
            system_flags.append({
                "severity": "WARNING",
                "code": "INVALID_SIGNAL_ROW",
                "message": "Baris sinyal bukan objek dan dilewati.",
                "row": index,
            })
            continue

        symbol = str(item.get("symbol", "")).strip().upper()
        score = _number(item.get("score"))
        rsi = _number(item.get("rsi_15m"))
        volume_ratio = _number(item.get("volume_ratio_15m"))
        trend_30m = item.get("trend_30m_bullish")
        trend_1h = item.get("trend_1h_bullish")

        row_errors = []
        if not symbol:
            row_errors.append("SYMBOL_MISSING")
        elif symbol in seen_symbols:
            row_errors.append("DUPLICATE_SYMBOL")
        else:
            seen_symbols.add(symbol)
        if score is None or not 0 <= score <= 100:
            row_errors.append("SCORE_INVALID")
        if rsi is None or not 0 <= rsi <= 100:
            row_errors.append("RSI_INVALID")
        if volume_ratio is None or volume_ratio < 0:
            row_errors.append("VOLUME_RATIO_INVALID")
        if not isinstance(trend_30m, bool) or not isinstance(trend_1h, bool):
            row_errors.append("TREND_CONFIRMATION_INVALID")

        if row_errors:
            invalid_rows += 1
            audited.append({
                "symbol": symbol or "UNKNOWN",
                "severity": "CRITICAL",
                "risk_flags": row_errors,
                "human_review_required": True,
                "decision": "BLOCKED",
            })
            continue

        risk_flags = []
        if score < 60:
            risk_flags.append("SCORE_BELOW_MINIMUM")
        if rsi >= 75:
            risk_flags.append("RSI_OVERBOUGHT")
        if volume_ratio < 1.5:
            risk_flags.append("VOLUME_CONFIRMATION_WEAK")
        if not trend_30m or not trend_1h:
            risk_flags.append("MULTI_TIMEFRAME_TREND_NOT_CONFIRMED")

        severity = "WARNING" if risk_flags else "INFO"
        audited.append({
            "symbol": symbol,
            "score": score,
            "rsi_15m": rsi,
            "volume_ratio_15m": volume_ratio,
            "severity": severity,
            "risk_flags": risk_flags,
            "human_review_required": bool(risk_flags),
            "decision": "REVIEW" if risk_flags else "MONITOR",
        })

    if invalid_rows:
        system_flags.append({
            "severity": "CRITICAL",
            "code": "INVALID_SIGNAL_DATA",
            "message": "Ada data sinyal tidak valid; hasil audit diblokir untuk tindakan lanjutan.",
            "count": invalid_rows,
        })

    critical = any(x["severity"] == "CRITICAL" for x in system_flags)
    warnings = any(x["severity"] == "WARNING" for x in system_flags)
    audit_status = "BLOCKED" if critical else ("CAUTION" if warnings else "CLEAR")

    recommendations = [
        "Audit ini hanya informasi untuk pemeriksaan manusia, bukan instruksi transaksi.",
        "Periksa spread, likuiditas, slippage, berita, dan risiko pasar secara terpisah.",
        "Jangan membuka transaksi berdasarkan laporan ini saja.",
    ]
    if audit_status == "BLOCKED":
        recommendations.insert(0, "Hentikan penggunaan hasil audit sampai masalah data atau mode diperbaiki.")
    elif audit_status == "CAUTION":
        recommendations.insert(0, "Tinjau kelengkapan pemindaian sebelum memakai hasilnya.")

    return {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ ONLY",
        "audit_status": audit_status,
        "source_version": report.get("version"),
        "source_scan_time_utc": report.get("scan_time_utc"),
        "source_universe_count": report.get("universe_count"),
        "audited_signal_count": len(audited),
        "warning_count": sum(x["severity"] == "WARNING" for x in audited),
        "review_count": sum(x["human_review_required"] for x in audited),
        "invalid_row_count": invalid_rows,
        "system_flags": system_flags,
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
    print("Status audit:", audited["audit_status"])
    print("Sinyal diaudit:", audited["audited_signal_count"])
    print("Peringatan sinyal:", audited["warning_count"])
    print("Perlu ditinjau:", audited["review_count"])
    print("Baris tidak valid:", audited["invalid_row_count"])
    print("Laporan:", output_file)
    print("Tidak ada order, wallet, atau akses broker.")
    return audited


if __name__ == "__main__":
    run()
