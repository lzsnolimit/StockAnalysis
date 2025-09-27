import os
import sqlite3
from scripts.db_writer import init_db, write_run_and_alerts


def test_sqlite_write_and_query(tmp_path):
    db_path = tmp_path / "attention.db"
    init_db(str(db_path))

    analyzed = {
        "items": [
            {
                "ticker": "AAPL",
                "data": {"quote": {"price": 100.0, "change_pct": 3.0}},
                "analysis": {
                    "attention_needed": True,
                    "severity": "alert",
                    "reasons": ["价格波动显著"],
                    "email": {"subject": "Subj AAPL", "body": "Body AAPL"},
                },
            },
            {
                "ticker": "TSLA",
                "data": {"quote": {"price": 200.0, "change_pct": -1.0}},
                "analysis": {
                    "attention_needed": False,
                    "severity": "watch",
                    "reasons": ["信号不足"],
                    "email": {"subject": "", "body": ""},
                },
            },
        ],
        "alerts": [
            {
                "ticker": "AAPL",
                "severity": "alert",
                "reasons": ["价格波动显著"],
                "email_subject": "Subj AAPL",
                "email_body": "Body AAPL",
            }
        ],
    }

    run_id = write_run_and_alerts(str(db_path), analyzed, run_ts="2025-09-27T10:00:00Z")
    assert run_id > 0

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT run_id, run_ts, alerts_count FROM runs WHERE run_id=?", (run_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[1] == "2025-09-27T10:00:00Z"
    assert row[2] == 1

    cur.execute("SELECT ticker, attention_needed, severity FROM alerts WHERE run_id=? ORDER BY ticker", (run_id,))
    rows = cur.fetchall()
    assert len(rows) == 2
    # AAPL attention_needed=1, TSLA=0
    assert rows[0][0] == "AAPL" and rows[0][1] == 1
    assert rows[1][0] == "TSLA" and rows[1][1] == 0

