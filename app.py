#!/usr/bin/env python3
"""HB Grid Stats Collector — FastAPI Dashboard for Hypergrid Business."""

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.database import (
    init_db, get_latest_snapshots, get_snapshots_by_month,
    get_available_months, get_all_grids, add_grid, remove_grid,
    toggle_grid, get_last_collection,
)
from src.collector import collect_all
from src.crawler import crawl_grid
from src.exporter import to_csv, to_markdown, to_html_table, to_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("hb-stats")

BASE_DIR = os.path.dirname(__file__)
scheduler = BackgroundScheduler(timezone="UTC")
_collecting = False
_collect_lock = threading.Lock()


def _scheduled_collect():
    global _collecting
    with _collect_lock:
        if _collecting:
            return
        _collecting = True
    try:
        collect_all(trigger="scheduled")
    finally:
        _collecting = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(
        _scheduled_collect,
        CronTrigger(day=1, hour=0, minute=1),
        id="monthly_collect",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — monthly collection on 1st at 00:01 UTC")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="HB Grid Stats Collector", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ── Jinja filters ────────────────────────────────────────────────────────

def _fmt_num(val):
    if val is None:
        return "—"
    try:
        return f"{int(val):,}"
    except (ValueError, TypeError):
        return "—"


def _fmt_land(sqm):
    if sqm is None:
        return "—"
    try:
        km2 = int(sqm) / 1_000_000
        return f"{km2:.2f} km²"
    except (ValueError, TypeError):
        return "—"


def _fmt_time(ts):
    if not ts:
        return "Never"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts


templates.env.filters["fnum"] = _fmt_num
templates.env.filters["fland"] = _fmt_land
templates.env.filters["ftime"] = _fmt_time


# ── Routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    snapshots = get_latest_snapshots()
    months = get_available_months()
    last = get_last_collection()

    # Next scheduled run
    job = scheduler.get_job("monthly_collect")
    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M UTC") if job and job.next_run_time else "—"

    online = sum(1 for s in snapshots if s.get("status") == "online")
    total = len(snapshots)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "snapshots": snapshots,
        "months": months,
        "online": online,
        "total": total,
        "last_collection": last,
        "next_collection": next_run,
        "now": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "collecting": _collecting,
    })


@app.post("/collect")
async def trigger_collect():
    global _collecting
    with _collect_lock:
        if _collecting:
            return RedirectResponse("/", status_code=303)
        _collecting = True
    try:
        collect_all(trigger="manual")
    finally:
        _collecting = False
    return RedirectResponse("/", status_code=303)


@app.get("/grids", response_class=HTMLResponse)
async def grids_page(request: Request):
    grids = get_all_grids()
    return templates.TemplateResponse("grids.html", {
        "request": request,
        "grids": grids,
    })


@app.post("/grids/add")
async def grid_add(name: str = Form(...), url: str = Form(...), format: str = Form("auto")):
    add_grid(name.strip(), url.strip(), format)
    return RedirectResponse("/grids", status_code=303)


@app.post("/grids/remove/{grid_id}")
async def grid_remove(grid_id: int):
    remove_grid(grid_id)
    return RedirectResponse("/grids", status_code=303)


@app.post("/grids/toggle/{grid_id}")
async def grid_toggle(grid_id: int):
    toggle_grid(grid_id)
    return RedirectResponse("/grids", status_code=303)


@app.post("/grids/test")
async def grid_test(url: str = Form(...)):
    """Test-crawl a URL and return parsed data as JSON."""
    data = crawl_grid("Test", url.strip(), "auto")
    return JSONResponse(data)


@app.get("/export/{fmt}")
async def export(fmt: str, month: str = None):
    if fmt not in ("csv", "markdown", "html", "json"):
        return Response("Invalid format", status_code=400)
    m = month or datetime.utcnow().strftime("%Y-%m")
    snapshots = get_snapshots_by_month(m)
    if not snapshots:
        return Response(f"No data for {m}", status_code=404)

    fn_map = {"csv": to_csv, "markdown": to_markdown, "html": to_html_table, "json": to_json}
    content = fn_map[fmt](snapshots, m)
    ext_map = {"csv": "csv", "markdown": "md", "html": "html", "json": "json"}
    ct_map = {
        "csv": "text/csv",
        "markdown": "text/markdown",
        "html": "text/html",
        "json": "application/json",
    }
    filename = f"grid_stats_{m}.{ext_map[fmt]}"
    return Response(
        content=content,
        media_type=ct_map[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "hb-grid-stats-collector", "version": "1.0.0"}


@app.get("/api/stats")
async def api_stats():
    return {"grids": get_latest_snapshots(), "months": get_available_months()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8051, reload=False)
