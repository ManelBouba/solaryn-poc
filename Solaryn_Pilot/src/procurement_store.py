"""Single-user local persistence. No authentication or tenant isolation claims."""
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import uuid


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, created TEXT, project TEXT, digest TEXT, payload TEXT)")
    return db


def save(path, result):
    payload = json.dumps(result, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    run_id = str(uuid.uuid4())
    with connect(path) as db:
        db.execute("INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
                   (run_id, datetime.now(timezone.utc).isoformat(), result["project"]["name"], digest, payload))
    return run_id


def history(path):
    with connect(path) as db:
        return db.execute("SELECT id, created, project, digest FROM decisions ORDER BY created DESC").fetchall()


def read(path, run_id):
    with connect(path) as db:
        row = db.execute("SELECT payload, digest FROM decisions WHERE id = ?", (run_id,)).fetchone()
    if not row or hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
        raise ValueError("Saved decision missing or integrity check failed")
    return json.loads(row[0])


def report(result):
    lines = ["# Solaryn procurement decision", "", result["project"]["name"], "", result["status"], "",
             "Deterministic, unlevered, pre-tax, constant-EUR scenarios. Not P50/P90 or procurement approval.",
             "", f"Model: {result['model_version']}", "",
             "| Candidate | NPV EUR | LCOE EUR/MWh | Lifetime MWh | Premium EUR/W vs first input |",
             "|---|---:|---:|---:|---:|"]
    for r in result["results"]:
        name = str(r["candidate"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {name} | {r['npv_eur']:.2f} | {r['lcoe_eur_mwh']:.2f} | {r['lifetime_mwh']:.2f} | {r['justified_premium_eur_w_vs_first']:.5f} |")
    lines += ["", "## Reproducible inputs and results", "", "```json", json.dumps(result, indent=2, allow_nan=False), "```"]
    return "\n".join(lines)
