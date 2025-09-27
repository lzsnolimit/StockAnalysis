import os
import sqlite3
import time
from typing import Dict, Any, List, Optional


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS runs (
      run_id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_ts TEXT NOT NULL,
      created_time TEXT,
      duration_ms INTEGER,
      top10_count INTEGER,
      alerts_count INTEGER,
      errors_json TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS alerts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id INTEGER NOT NULL,
      ticker TEXT NOT NULL,
      severity TEXT,
      attention_needed INTEGER NOT NULL,
      reasons_json TEXT,
      email_subject TEXT,
      email_body TEXT,
      price REAL,
      change_pct REAL,
      news_count INTEGER,
      data_snapshot_json TEXT,
      created_at TEXT,
      created_time TEXT,
      UNIQUE(run_id, ticker),
      FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_alerts_run ON alerts(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts(ticker);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_attn ON alerts(attention_needed, severity);",
]


def _get_db_path(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    # Support DB_PATH override, else fall back to SQLITE_PATH, else default
    return os.environ.get("DB_PATH") or os.environ.get("SQLITE_PATH", "data/attention.db")


def _connect(sqlite_path: Optional[str]) -> sqlite3.Connection:
    path = _get_db_path(sqlite_path)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path)
    return conn


def init_db(sqlite_path: str) -> None:
    with _connect(sqlite_path) as conn:
        cur = conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        _ensure_schema_upgrades(cur)
        conn.commit()


def _ensure_schema_upgrades(cur: sqlite3.Cursor) -> None:
    # Add created_time columns if they don't exist (best-effort)
    try:
        cur.execute("PRAGMA table_info(runs)")
        cols = [r[1] for r in cur.fetchall()]
        if "created_time" not in cols:
            cur.execute("ALTER TABLE runs ADD COLUMN created_time TEXT")
    except Exception:
        pass
    try:
        cur.execute("PRAGMA table_info(alerts)")
        cols = [r[1] for r in cur.fetchall()]
        if "created_time" not in cols:
            cur.execute("ALTER TABLE alerts ADD COLUMN created_time TEXT")
    except Exception:
        pass


def write_run_and_alerts(sqlite_path: Optional[str], analyzed: Dict[str, Any], run_ts: str | None = None, errors: List[str] | None = None) -> int:
    run_ts = run_ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    items = analyzed.get("items", [])
    alerts = analyzed.get("alerts", [])
    errors_json = None
    if errors:
        import json

        errors_json = json.dumps(errors, ensure_ascii=False)

    with _connect(sqlite_path) as conn:
        cur = conn.cursor()
        # ensure schema
        for stmt in SCHEMA:
            cur.execute(stmt)
        _ensure_schema_upgrades(cur)
        # insert run
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cur.execute(
            "INSERT INTO runs(run_ts, created_time, duration_ms, top10_count, alerts_count, errors_json) VALUES (?,?,?,?,?,?)",
            (run_ts, now, None, len(items), len(alerts), errors_json),
        )
        run_id = cur.lastrowid

        # insert alerts
        import json

        for item in items:
            ticker = item.get("ticker")
            decision = item.get("analysis", {})
            attn = 1 if decision.get("attention_needed") else 0
            severity = decision.get("severity")
            reasons_json = json.dumps(decision.get("reasons", []), ensure_ascii=False)
            email = decision.get("email") or {}
            email_subject = email.get("subject")
            email_body = email.get("body")
            quote = (item.get("data") or {}).get("quote") or {}
            price = quote.get("price")
            change_pct = quote.get("change_pct")
            # news_count can be derived from optional news list in snapshot if present
            news_count = None
            snapshot = json.dumps(item, ensure_ascii=False)
            cur.execute(
                """
                INSERT OR REPLACE INTO alerts(run_id, ticker, severity, attention_needed, reasons_json, email_subject, email_body, price, change_pct, news_count, data_snapshot_json, created_at, created_time)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (run_id, ticker, severity, attn, reasons_json, email_subject, email_body, price, change_pct, news_count, snapshot, run_ts, now),
            )
        conn.commit()
        return run_id
