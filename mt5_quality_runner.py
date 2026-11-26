"""Build a fail-closed MT5 quality report from an optional Exness export."""
import json
import os

from mt5_readonly_adapter import normalize_export
from mt5_data_quality import assess_export_quality

INPUT_FILE = "v9_mt5_readonly_snapshot.json"
OUTPUT_FILE = "mt5_data_quality_report.json"


def build_quality_report(raw_export):
    normalized = normalize_export(raw_export)
    return assess_export_quality(normalized)


def run(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    if not os.path.exists(input_file):
        report = {
            "status": "DATA_NOT_AVAILABLE",
            "message": "No MT5 export supplied. Exporter has not yet been run on a verified Exness MT5 terminal.",
            "snapshot_count": 0,
            "results": [],
            "mode": "READ ONLY",
            "orders_enabled": False,
            "new_risk_allowed": False,
            "automated_trade_instruction": False,
        }
    else:
        with open(input_file, "r", encoding="utf-8") as handle:
            raw_export = json.load(handle)
        report = build_quality_report(raw_export)

    temporary = output_file + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output_file)
    print("MT5 quality report:", output_file, "status:", report.get("status", "READY"))
    print("READ ONLY - orders disabled.")
    return report


if __name__ == "__main__":
    run()
