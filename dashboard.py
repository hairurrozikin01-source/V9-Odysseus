"""Generate a self-contained, mobile-first Indonesian V9 dashboard.

The dashboard is a static report viewer. It does not connect to brokers,
wallets, exchanges, or place orders.
"""
import html
import json
import os
from datetime import datetime, timezone

FILES = {
    "v9": "v9_scan_results.json",
    "shib": "shib_hunter_results.json",
    "odysseus": "odysseus_audit_report.json",
    "risk": "v9_risk_monitor_report.json",
}
OUTPUT_FILE = "v9_dashboard.html"


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _safe(value):
    return html.escape(str(value if value is not None else "—"), quote=True)


def build_dashboard(reports, generated_at=None):
    """Build HTML from report dictionaries; missing reports are shown explicitly."""
    reports = reports if isinstance(reports, dict) else {}
    v9 = reports.get("v9") if isinstance(reports.get("v9"), dict) else {}
    shib = reports.get("shib") if isinstance(reports.get("shib"), dict) else {}
    ody = reports.get("odysseus") if isinstance(reports.get("odysseus"), dict) else {}
    risk = reports.get("risk") if isinstance(reports.get("risk"), dict) else {}

    signals = v9.get("results") if isinstance(v9.get("results"), list) else []
    candidates = shib.get("candidates") if isinstance(shib.get("candidates"), list) else []
    audits = ody.get("audited_signals") if isinstance(ody.get("audited_signals"), list) else []
    flags = risk.get("flags") if isinstance(risk.get("flags"), list) else []
    watchlist = [x for x in candidates if isinstance(x, dict) and x.get("decision") == "WATCHLIST"]

    risk_level = risk.get("risk_level", "DATA BELUM TERSEDIA")
    risk_class = "good" if risk_level == "OBSERVE" else ("bad" if risk_level == "BLOCKED" else "warn")
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    signal_rows = []
    for item in signals[:30]:
        if not isinstance(item, dict):
            continue
        signal_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _safe(item.get("symbol")), _safe(item.get("score")),
                _safe(item.get("rsi_15m")), _safe(item.get("status")),
            )
        )
    if not signal_rows:
        signal_rows = ['<tr><td colspan="4" class="muted">Belum ada data sinyal V9.</td></tr>']

    token_rows = []
    for item in watchlist[:30]:
        token_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _safe(item.get("symbol") or item.get("name")),
                _safe(item.get("chain_id")), _safe(item.get("score")),
                _safe(item.get("security_status", "BELUM TERVERIFIKASI")),
            )
        )
    if not token_rows:
        token_rows = ['<tr><td colspan="4" class="muted">Belum ada kandidat watchlist.</td></tr>']

    flag_rows = []
    for item in flags[:30]:
        if isinstance(item, dict):
            flag_rows.append(
                "<li><b>{}</b> — {}</li>".format(
                    _safe(item.get("severity")), _safe(item.get("message"))
                )
            )
    if not flag_rows:
        flag_rows = ['<li class="muted">Tidak ada peringatan yang tercatat, atau laporan belum tersedia.</li>']

    missing = [key for key in FILES if not isinstance(reports.get(key), dict)]
    data_note = (
        "Laporan belum tersedia: " + ", ".join(missing) + "."
        if missing else "Semua empat laporan tersedia untuk sesi ini."
    )

    return """<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b1020"><title>V9 Odysseus — Dashboard</title>
<style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#121a2d;--line:#26334d;--text:#edf2ff;--muted:#9aa9c2;--cyan:#65d5df}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1050px;margin:auto;padding:22px 16px 48px}.top{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:25px;margin:0}h2{font-size:17px;margin:0 0 12px}.sub,.muted{color:var(--muted);font-size:13px}
.pill{display:inline-block;padding:5px 10px;border:1px solid var(--line);border-radius:99px;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:18px 0}
.card,section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px;margin-bottom:13px}
.metric{font-size:25px;font-weight:700;margin-top:5px}.good{color:#78dfac}.warn{color:#ffd27a}.bad{color:#ff8585}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:9px 7px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:600}
.tablewrap{overflow-x:auto}ul{padding-left:20px;margin:0}li{margin:8px 0}.notice{border-left:3px solid var(--cyan);padding:10px 12px;background:#101d30;border-radius:6px;margin:14px 0}
footer{color:var(--muted);font-size:12px;margin-top:22px}
@media(max-width:650px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:17px 12px 35px}h1{font-size:22px}}
</style></head><body><main>
<header class="top"><div><h1>V9 <span style="color:var(--cyan)">Odysseus</span></h1><div class="sub">Dashboard pemantauan • Bahasa Indonesia • {generated_at}</div></div><span class="pill">MODE READ ONLY</span></header>
<div class="notice">Dashboard ini hanya menampilkan laporan analisis. Tidak ada koneksi broker, akses wallet, atau kemampuan mengirim transaksi.</div>
<div class="grid">
<div class="card"><div class="sub">Sinyal V9</div><div class="metric">{len(signals)}</div></div>
<div class="card"><div class="sub">Kandidat SHIB Hunter</div><div class="metric">{len(watchlist)}</div></div>
<div class="card"><div class="sub">Audit Odysseus</div><div class="metric">{len(audits)}</div></div>
<div class="card"><div class="sub">Peringatan Risiko</div><div class="metric">{len(flags)}</div></div>
</div>
<section><h2>Status Risk Monitor</h2><div class="metric {risk_class}">{_safe(risk_level)}</div><p class="sub">{_safe(risk.get("summary", "Laporan risiko belum tersedia."))}</p><div class="sub">{_safe(data_note)}</div></section>
<section><h2>Peringatan dan pemeriksaan</h2><ul>{''.join(flag_rows)}</ul></section>
<section><h2>Hasil analisis V9 — maksimal 30</h2><div class="tablewrap"><table><thead><tr><th>Simbol</th><th>Skor</th><th>RSI 15m</th><th>Status</th></tr></thead><tbody>{''.join(signal_rows)}</tbody></table></div></section>
<section><h2>SHIB Hunter — daftar pantauan</h2><div class="tablewrap"><table><thead><tr><th>Token</th><th>Chain</th><th>Skor</th><th>Keamanan</th></tr></thead><tbody>{''.join(token_rows)}</tbody></table></div><p class="sub">Kandidat watchlist bukan rekomendasi beli. Status keamanan yang belum terverifikasi memerlukan pemeriksaan independen.</p></section>
<section><h2>Batasan sistem</h2><ul><li>Data berasal dari laporan pemindaian pada satu eksekusi GitHub Actions.</li><li>SHIB Hunter bukan pemindai seluruh token dan bukan audit keamanan kontrak.</li><li>Risk Monitor saat ini memeriksa integritas laporan dan peringatan, bukan risiko portofolio atau drawdown akun.</li><li>Belum ada estimasi profit, win rate, atau jaminan hasil.</li><li>Data Gold/Forex MT5 belum aktif sampai exporter diuji pada terminal Windows.</li></ul></section>
<footer>V9 Odysseus • Dibuat otomatis oleh GitHub Actions • {generated_at}</footer>
</main></body></html>""".format(
        generated_at=_safe(generated_at), len=len, signals=signals,
        watchlist=watchlist, audits=audits, flags=flags, risk_class=risk_class,
        risk_level=risk_level, risk=risk, data_note=_safe(data_note),
        flag_rows="".join(flag_rows), signal_rows="".join(signal_rows),
        token_rows="".join(token_rows),
    )


def run(output_file=OUTPUT_FILE):
    reports = {key: _load(path) for key, path in FILES.items()}
    page = build_dashboard(reports)
    temporary = output_file + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(page)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output_file)
    print("Dashboard:", output_file)
    print("READ ONLY - no broker, wallet, or transaction access.")
    return output_file


if __name__ == "__main__":
    run()
