import os
import sqlite3
from typing import Tuple, Dict, Any, List


def connect(sqlite_path: str | None = None) -> sqlite3.Connection:
    path = sqlite_path or os.environ.get("SQLITE_PATH", "data/attention.db")
    return sqlite3.connect(path)


def get_latest_run(conn: sqlite3.Connection) -> Tuple[int | None, Dict[str, Any] | None]:
    cur = conn.cursor()
    cur.execute("SELECT run_id, run_ts, alerts_count FROM runs ORDER BY run_id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return None, None
    return row[0], {"run_id": row[0], "run_ts": row[1], "alerts_count": row[2]}


def get_alerts_for_run(conn: sqlite3.Connection, run_id: int) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        "SELECT ticker, severity, attention_needed, reasons_json, email_subject, email_body, price, change_pct, news_count FROM alerts WHERE run_id=? AND attention_needed=1 ORDER BY severity DESC, ticker ASC",
        (run_id,),
    )
    rows = cur.fetchall()
    items: List[Dict[str, Any]] = []
    import json

    for r in rows:
        reasons = []
        try:
            reasons = json.loads(r[3] or "[]")
        except Exception:
            reasons = []
        items.append(
            {
                "ticker": r[0],
                "severity": r[1],
                "reasons": reasons,
                "email_subject": r[4],
                "email_body": r[5],
                "price": r[6],
                "change_pct": r[7],
                "news_count": r[8],
            }
        )
    return items

