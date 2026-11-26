"""V9.5.2 read-only cross-module risk monitor.

This module summarizes data-quality and screening warnings from V9 and SHIB
Hunter. It is not a portfolio-risk model, price predictor, or trading system.
"""
import json
import os
from datetime import datetime, timezone

VERSION = "V9-RISK-MONITOR-0.1.0"
V9_INPUT = "v9_scan_results.json"
SHIB_INPUT = "shib_hunter_results.json"
OUTPUT_FILE = "v9_risk_monitor_report.json"


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _count(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("{} must be a non-negative integer".format(field))
    return value


def evaluate_risk(v9_report, shib_report):
    """Return a conservative status from the two read-only scan reports."""
    if not isinstance(v9_report, dict) or not isinstance(shib_report, dict):
        raise ValueError("Input reports must be JSON objects")

    flags = []
    critical = False

    for label, report in (("V9", v9_report), ("SHIB_HUNTER", shib_report)):
        if str(report.get("mode", "")).upper() != "READ ONLY":
            critical = True
            flags.append({
                "severity": "CRITICAL",
                "code": label + "_MODE_NOT_READ_ONLY",
                "message": label + " report is not marked READ ONLY.",
            })

    v9_results = v9_report.get("results")
    v9_failures = v9_report.get("failures")
    if not isinstance(v9_results, list) or not isinstance(v9_failures, list):
        raise ValueError("V9 results and failures must be lists")

    v9_failed_count = _count(v9_report.get("failed_count"), "V9 failed_count")
    if v9_failed_count != len(v9_failures):
        critical = True
        flags.append({
            "severity": "CRITICAL",
            "code": "V9_FAILURE_COUNT_MISMATCH",
            "message": "V9 failed_count does not match its failures list.",
        })
    elif v9_failed_count:
        flags.append({
            "severity": "WARNING",
            "code": "V9_ANALYSIS_FAILURES",
            "message": "Some V9 symbols could not be analyzed.",
            "count": v9_failed_count,
        })

    shib_candidates = shib_report.get("candidates")
    shib_failures = shib_report.get("failures")
    if not isinstance(shib_candidates, list) or not isinstance(shib_failures, list):
        raise ValueError("SHIB Hunter candidates and failures must be lists")

    shib_failed_count = _count(shib_report.get("failure_count"), "SHIB failure_count")
    if shib_failed_count != len(shib_failures):
        critical = True
        flags.append({
            "severity": "CRITICAL",
            "code": "SHIB_FAILURE_COUNT_MISMATCH",
            "message": "SHIB Hunter failure_count does not match its failures list.",
        })
    elif shib_failed_count:
        flags.append({
            "severity": "WARNING",
            "code": "SHIB_ENRICHMENT_FAILURES",
            "message": "Some SHIB Hunter token lookups failed.",
            "count": shib_failed_count,
        })

    watchlist = [x for x in shib_candidates
                 if isinstance(x, dict) and x.get("decision") == "WATCHLIST"]
    unverified = [x for x in watchlist
                  if x.get("security_status") != "VERIFIED"]
    if unverified:
        flags.append({
            "severity": "WARNING",
            "code": "TOKEN_SECURITY_NOT_VERIFIED",
            "message": "Watchlist tokens have not passed a full security audit.",
            "count": len(unverified),
        })

    if critical:
        level = "BLOCKED"
        summary = "Input integrity or execution-mode issue; do not rely on this report."
    elif flags:
        level = "CAUTION"
        summary = "Review data-quality and token-security warnings before interpreting candidates."
    else:
        level = "OBSERVE"
        summary = "No structural warning detected; this is not a safety or profitability guarantee."

    return {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ ONLY",
        "risk_level": level,
        "summary": summary,
        "source_versions": {
            "v9": v9_report.get("version"),
            "shib_hunter": shib_report.get("version"),
        },
        "metrics": {
            "v9_signal_count": len(v9_results),
            "v9_failure_count": v9_failed_count,
            "shib_candidate_count": len(shib_candidates),
            "shib_watchlist_count": len(watchlist),
            "shib_failure_count": shib_failed_count,
            "watchlist_security_unverified_count": len(unverified),
        },
        "flags": flags,
        "limitations": [
            "This report checks scan integrity and screening warnings, not account or portfolio exposure.",
            "SHIB Hunter discovery is not exhaustive and token security is not fully verified.",
            "No price prediction, expected return, or win-rate estimate is produced.",
            "A human must perform independent due diligence before any investment decision.",
        ],
        "safety": {
            "orders_enabled": False,
            "wallet_access": False,
            "broker_credentials_required": False,
            "automated_trade_instruction": False,
        },
    }


def save_report(report, filename=OUTPUT_FILE):
    temporary = filename + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, filename)


def run(v9_file=V9_INPUT, shib_file=SHIB_INPUT, output_file=OUTPUT_FILE):
    result = evaluate_risk(_load_json(v9_file), _load_json(shib_file))
    save_report(result, output_file)
    print("V9 Risk Monitor", VERSION, "| READ ONLY")
    print("Risk level:", result["risk_level"])
    print("Flags:", len(result["flags"]))
    print("Report:", output_file)
    print("No orders, wallet access, or broker credentials.")
    return result


if __name__ == "__main__":
    run()
