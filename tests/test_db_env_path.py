import os
import sqlite3
from scripts.db_writer import write_run_and_alerts, init_db


def test_write_uses_env_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "envdb.sqlite"
    monkeypatch.setenv("DB_PATH", str(db_path))
    # Ensure DB created
    init_db(None if hasattr(init_db, "__call__") else str(db_path))

    analyzed = {
        "items": [
            {"ticker": "AAPL", "data": {"quote": {}}, "analysis": {"attention_needed": True, "severity": "watch", "reasons": [], "email": {"subject": "s", "body": "b"}}}
        ],
        "alerts": [
            {"ticker": "AAPL", "severity": "watch", "reasons": [], "email_subject": "s", "email_body": "b"}
        ],
    }
    run_id = write_run_and_alerts(None, analyzed, run_ts="2025-09-27T12:00:00Z")
    assert run_id > 0

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM alerts WHERE run_id=?", (run_id,))
    assert cur.fetchone()[0] == 1

