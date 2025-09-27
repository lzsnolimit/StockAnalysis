import os
from flask import Flask, jsonify
from server.db import connect, get_latest_run, get_alerts_for_run


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/alerts/latest")
    def alerts_latest():
        try:
            with connect() as conn:
                run_id, run = get_latest_run(conn)
                if not run_id:
                    return jsonify({"error": "no runs"}), 404
                items = get_alerts_for_run(conn, run_id)
                return jsonify({"run": run, "items": items})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/alerts/latest/summary")
    def alerts_latest_summary():
        try:
            with connect() as conn:
                run_id, run = get_latest_run(conn)
                if not run_id:
                    return jsonify({"error": "no runs"}), 404
                items = get_alerts_for_run(conn, run_id)
                by_severity = {"watch": 0, "alert": 0}
                for it in items:
                    sev = it.get("severity") or "watch"
                    by_severity[sev] = by_severity.get(sev, 0) + 1
                return jsonify({
                    "run_id": run_id,
                    "run_ts": run["run_ts"],
                    "total_items": len(items),
                    "attention_items": len(items),
                    "by_severity": by_severity,
                })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", "8000"))
    app = create_app()
    app.run(host="0.0.0.0", port=port)

