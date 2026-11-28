"""Publish V9 read-only scan and operational-risk reports to Supabase Edge Function."""
import json
import os
import sys
import urllib.error
import urllib.request

V9_REPORT = "v9_scan_results.json"
RISK_REPORT = "v9_risk_monitor_report.json"


def build_payload(v9_report, risk_report):
    """Validate the report boundary and return a UTF-8 JSON payload."""
    if not isinstance(v9_report, dict) or not isinstance(risk_report, dict):
        raise ValueError("Both reports must be JSON objects.")
    if v9_report.get("mode") != "READ ONLY" or risk_report.get("mode") != "READ ONLY":
        raise RuntimeError("Refusing to publish reports not explicitly marked READ ONLY.")
    return json.dumps({
        "v9_report": v9_report,
        "risk_report": risk_report,
    }).encode("utf-8")


def main():
    endpoint = os.environ.get("V9_INGEST_URL", "").strip()
    secret = os.environ.get("V9_INGEST_KEY", "").strip()
    if not endpoint or not secret:
        print("V9 ingestion skipped: configure V9_INGEST_URL and V9_INGEST_KEY in GitHub Actions secrets.")
        return 0

    with open(V9_REPORT, "r", encoding="utf-8") as handle:
        v9_report = json.load(handle)
    with open(RISK_REPORT, "r", encoding="utf-8") as handle:
        risk_report = json.load(handle)

    payload = build_payload(v9_report, risk_report)
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-v9-ingest-key": secret,
            "User-Agent": "V9-Odysseus-ReadOnly-Ingest/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            if response.status != 200 or result.get("ok") is not True:
                raise RuntimeError("Ingestion endpoint did not confirm success.")
            print(json.dumps(result, indent=2))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError("Supabase ingestion failed (HTTP {}): {}".format(exc.code, detail)) from exc

    return 0


if __name__ == "__main__":
    sys.exit(main())
