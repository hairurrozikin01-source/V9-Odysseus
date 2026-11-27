"""Build a read-only MT5 data-quality report from an optional Exness export."""
import json
import os

from mt5_readonly_adapter import normalize_export, SnapshotValidationError
from mt5_data_quality import assess_export_quality

INPUT_FILE = "v9_mt5_readonly_snapshot.json"
OUTPUT_FILE = "mt5_data_quality_report.json"


def build_report(raw_export):
    """Validate the MT5 export before assessing each symbol's data quality."""
    normalized = normalize_export(raw_export)
    report = assess_export_quality(normalized)
    report["source_file"] = INPUT_FILE
    report["source_exported_at_utc"] = normalized["exported_at_utc"]
    return report


def run(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    if not os.path.exists(input_file):
        report = {
            "version": "V9-MT5-DATA-QUALITY-0.1.0",
            "broker": "Exness",
            "account_type": "Raw Spread",
            "platform": "MT5",
            "mode": "READ ONLY",
            "status": "DATA_NOT_AVAILABLE",
            "message": "No MT5 export supplied to this GitHub Actions run.",
            "snapshot_count": 0,
            "results": [],
            "orders_enabled": False,
            "new_risk_allowed": False,
            "automated_trade_instruction": False,
        }
    else:
        try:
            with open(input_file, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            report = build_report(raw)
            report["status"] = (
                "BLOCKED" if report["blocked_count"] else
                "WARNING" if report["warning_count"] else "PASS"
            )
        except (OSError, ValueError, SnapshotValidationError) as exc:
            report = {
                "version": "V9-MT5-DATA-QUALITY-0.1.0",
                "broker": "Exness",
                "account_type": "Raw Spread",
                "platform": "MT5",
                "mode": "READ ONLY",
                "status": "BLOCKED_INVALID_EXPORT",
                "message": str(exc),
                "snapshot_count": 0,
                "results": [],
                "orders_enabled": False,
                "new_risk_allowed": False,
                "automated_trade_instruction": False,
            }

    temporary = output_file + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output_file)
    print("MT5 quality report:", report.get("status"))
    print("READ ONLY - no orders or new risk authorization.")
    return report


if __name__ == "__main__":
    run()
