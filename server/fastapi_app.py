import os
from fastapi import FastAPI, HTTPException
from server.db import connect, get_latest_run_full, get_items_for_run_all


app = FastAPI(title="Stock Analysis API", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/runs/latest/items")
def latest_run_items():
    """Return latest run metadata and all items (including non-attention) for frontend display."""
    try:
        with connect() as conn:
            run_id, run = get_latest_run_full(conn)
            if not run_id:
                raise HTTPException(status_code=404, detail="no runs")
            items = get_items_for_run_all(conn, run_id)
            return {"run": run, "items": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Optional dev runner with uvicorn
    import uvicorn

    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run("server.fastapi_app:app", host="0.0.0.0", port=port, reload=False)

