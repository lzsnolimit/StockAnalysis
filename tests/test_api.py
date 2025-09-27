import os
from server.app import create_app
from scripts.db_writer import init_db, write_run_and_alerts


def seed_db(path):
    init_db(path)
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
            }
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
    write_run_and_alerts(path, analyzed, run_ts="2025-09-27T11:00:00Z")


def test_api_latest_endpoints(tmp_path, monkeypatch):
    db_path = str(tmp_path / "attention.db")
    seed_db(db_path)
    monkeypatch.setenv("SQLITE_PATH", db_path)

    app = create_app()
    client = app.test_client()

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json["status"] == "ok"

    r = client.get("/alerts/latest")
    assert r.status_code == 200
    assert r.json["run"]["alerts_count"] == 1
    assert len(r.json["items"]) == 1
    assert r.json["items"][0]["ticker"] == "AAPL"

    r = client.get("/alerts/latest/summary")
    assert r.status_code == 200
    assert r.json["attention_items"] == 1
    assert r.json["by_severity"]["alert"] == 1

