# HB Grid Stats Collector

Automated monthly stats collector for [Hypergrid Business](https://hypergridbusiness.com) — the leading publication covering the OpenSimulator ecosystem.

Replaces the manual process of visiting dozens of grid websites every month to collect stats. Runs as a hosted web service — no installation required on the user's end.

**Live instance:** [thinksim.space/hb](https://thinksim.space/hb)

## What It Does

- **Universal Crawler** — automatically detects and parses three common OpenSim stats formats:
  - Diva Distro WiFi pages (`/wifi`)
  - Plain-text grid_info (`/grid_info`)
  - JSON APIs (`/api/stats`)
- **Monthly Auto-Collection** — runs automatically on the 1st of every month at 00:01 UTC
- **One-Click Manual Collection** — collect all grids instantly from the dashboard
- **Export Ready** — download data as CSV, Markdown table, HTML table, or JSON
- **Web Management** — add, remove, and test grids from the browser (no config files)
- **Historical Data** — every collection is stored; export any past month

## Pre-loaded Grids

Comes with 8 major OpenSim grids pre-configured:

| Grid | Format |
|------|--------|
| ThinkSim | JSON API |
| Kitely | Plain text |
| OSgrid | Diva WiFi |
| DigiWorldz | Diva WiFi |
| ZetaWorlds | Diva WiFi |
| Craft World | Diva WiFi |
| Alternate Metaverse | Diva WiFi |
| Great Canadian Grid | Diva WiFi |

## Self-Hosting

### Quick Start (Docker)

```bash
git clone https://github.com/thinkneo-ai/hb-grid-stats-collector.git
cd hb-grid-stats-collector
docker compose up -d
```

Dashboard at `http://localhost:8051`

### Without Docker

```bash
git clone https://github.com/thinkneo-ai/hb-grid-stats-collector.git
cd hb-grid-stats-collector
pip install -r requirements.txt
python app.py
```

Dashboard at `http://localhost:8051`

### Nginx Reverse Proxy

To serve at `/hb` on your domain:

```nginx
location /hb/ {
    proxy_pass http://127.0.0.1:8051/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Usage

### Dashboard

Open the dashboard in your browser. From there you can:

- See all grids with their current stats (green = online, red = offline)
- Click **Collect All Now** to run a manual collection
- Download data in CSV, Markdown, HTML, or JSON

### Manage Grids

Click **Manage Grids** to:

- **Add a grid** — type the name and URL, format is auto-detected
- **Test a URL** — paste any URL to preview what data the crawler finds
- **Enable/Disable** — toggle grids without removing them
- **Remove** — permanently delete a grid from the list

### API

- `GET /health` — service health check
- `GET /api/stats` — JSON with latest stats for all grids
- `GET /export/csv?month=2026-04` — download CSV for a specific month
- `GET /export/markdown?month=2026-04` — download Markdown table
- `GET /export/html?month=2026-04` — download HTML table
- `GET /export/json?month=2026-04` — download JSON export

## Data Fields

| Field | Description |
|-------|-------------|
| `grid_name` | Display name of the grid |
| `total_regions` | Number of regions/sims |
| `active_users_30d` | Users active in the last 30 days |
| `online_users_now` | Users currently online |
| `total_users` | Total registered accounts |
| `land_sqm` | Total land area in square meters |
| `status` | `online`, `error`, or `unknown` |
| `collected_at` | Timestamp of collection (UTC) |

## Tech Stack

- **Python 3.12** + FastAPI + Uvicorn
- **SQLite** — zero-config database
- **APScheduler** — monthly cron
- **BeautifulSoup + lxml** — HTML parsing
- **Jinja2** — server-side templates
- **Docker** — single-container deployment

## License

MIT — [ThinkNEO AI](https://thinkneo.ai)
