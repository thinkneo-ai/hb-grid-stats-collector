"""SQLite database for grid registry and stats history."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stats.db")

# Default grids to pre-populate on first run
DEFAULT_GRIDS = [
    {"name": "ThinkSim", "url": "https://thinksim.space/grid_info", "format": "auto"},
    {"name": "Kitely", "url": "https://www.kitely.com/grid_info", "format": "auto"},
    {"name": "OSgrid", "url": "http://login.osgrid.org:8002/wifi", "format": "auto"},
    {"name": "DigiWorldz", "url": "http://login.digiworldz.com:8002/wifi", "format": "auto"},
    {"name": "ZetaWorlds", "url": "http://login.zetaworlds.com:8002/wifi", "format": "auto"},
    {"name": "Craft World", "url": "http://craft-world.org:8002/wifi", "format": "auto"},
    {"name": "Alternate Metaverse", "url": "http://login.alternatemetaverse.com:8002/wifi", "format": "auto"},
    {"name": "Great Canadian Grid", "url": "http://login.greatcanadiangrid.ca:8002/wifi", "format": "auto"},
]


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS grids (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            url         TEXT    NOT NULL,
            format      TEXT    NOT NULL DEFAULT 'auto',
            enabled     INTEGER NOT NULL DEFAULT 1,
            added_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            grid_id             INTEGER NOT NULL REFERENCES grids(id),
            grid_name           TEXT    NOT NULL,
            total_regions       INTEGER,
            active_users_30d    INTEGER,
            online_users_now    INTEGER,
            total_users         INTEGER,
            land_sqm            INTEGER,
            status              TEXT    NOT NULL DEFAULT 'unknown',
            error_msg           TEXT,
            collected_at        TEXT    NOT NULL,
            month               TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_snap_grid_month ON snapshots(grid_name, month);
        CREATE INDEX IF NOT EXISTS idx_snap_month ON snapshots(month);

        CREATE TABLE IF NOT EXISTS collection_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at      TEXT NOT NULL,
            finished_at     TEXT,
            grids_total     INTEGER,
            grids_online    INTEGER,
            trigger         TEXT NOT NULL DEFAULT 'manual'
        );
    """)
    conn.close()
    _seed_defaults()


def _seed_defaults():
    conn = get_conn()
    existing = conn.execute("SELECT COUNT(*) as c FROM grids").fetchone()["c"]
    if existing == 0:
        now = datetime.utcnow().isoformat()
        for g in DEFAULT_GRIDS:
            conn.execute(
                "INSERT INTO grids (name, url, format, enabled, added_at) VALUES (?, ?, ?, 1, ?)",
                (g["name"], g["url"], g["format"], now),
            )
        conn.commit()
    conn.close()


# ── Grid CRUD ────────────────────────────────────────────────────────────

def get_all_grids():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM grids ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_enabled_grids():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM grids WHERE enabled = 1 ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_grid(name: str, url: str, fmt: str = "auto") -> dict | None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO grids (name, url, format, enabled, added_at) VALUES (?, ?, ?, 1, ?)",
            (name, url, fmt, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM grids WHERE name = ?", (name,)).fetchone()
        conn.close()
        return dict(row)
    except sqlite3.IntegrityError:
        conn.close()
        return None


def remove_grid(grid_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM grids WHERE id = ?", (grid_id,))
    conn.commit()
    conn.close()


def toggle_grid(grid_id: int):
    conn = get_conn()
    conn.execute("UPDATE grids SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id = ?", (grid_id,))
    conn.commit()
    conn.close()


# ── Snapshots ────────────────────────────────────────────────────────────

def save_snapshot(grid_id: int, data: dict):
    conn = get_conn()
    now = datetime.utcnow().isoformat()
    month = now[:7]
    conn.execute("""
        INSERT INTO snapshots
            (grid_id, grid_name, total_regions, active_users_30d, online_users_now,
             total_users, land_sqm, status, error_msg, collected_at, month)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        grid_id,
        data.get("grid_name", "Unknown"),
        data.get("total_regions"),
        data.get("active_users_30d"),
        data.get("online_users_now"),
        data.get("total_users"),
        data.get("land_sqm"),
        data.get("status", "unknown"),
        data.get("error_msg"),
        now,
        month,
    ))
    conn.commit()
    conn.close()


def get_latest_snapshots():
    """Most recent snapshot for each grid, joined with grid info."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT g.id as grid_id, g.name, g.url, g.format, g.enabled,
               s.total_regions, s.active_users_30d, s.online_users_now,
               s.total_users, s.land_sqm, s.status, s.error_msg, s.collected_at
        FROM grids g
        LEFT JOIN (
            SELECT s1.* FROM snapshots s1
            INNER JOIN (
                SELECT grid_id, MAX(collected_at) as max_ts
                FROM snapshots GROUP BY grid_id
            ) s2 ON s1.grid_id = s2.grid_id AND s1.collected_at = s2.max_ts
        ) s ON g.id = s.grid_id
        ORDER BY g.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_snapshots_by_month(month: str):
    """Latest snapshot per grid for a given month."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.* FROM snapshots s
        INNER JOIN (
            SELECT grid_id, MAX(collected_at) as max_ts
            FROM snapshots WHERE month = ? GROUP BY grid_id
        ) latest ON s.grid_id = latest.grid_id AND s.collected_at = latest.max_ts
        ORDER BY s.grid_name
    """, (month,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_available_months():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT month FROM snapshots ORDER BY month DESC").fetchall()
    conn.close()
    return [r["month"] for r in rows]


# ── Collection log ───────────────────────────────────────────────────────

def log_collection_start(trigger: str = "manual") -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO collection_log (started_at, trigger) VALUES (?, ?)",
        (datetime.utcnow().isoformat(), trigger),
    )
    conn.commit()
    log_id = cur.lastrowid
    conn.close()
    return log_id


def log_collection_end(log_id: int, total: int, online: int):
    conn = get_conn()
    conn.execute(
        "UPDATE collection_log SET finished_at = ?, grids_total = ?, grids_online = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), total, online, log_id),
    )
    conn.commit()
    conn.close()


def get_last_collection():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM collection_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None
