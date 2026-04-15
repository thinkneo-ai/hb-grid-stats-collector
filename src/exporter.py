"""Export grid stats to CSV, JSON, Markdown, and HTML table formats."""

import csv
import json
import io
import os
from datetime import datetime

EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")

COLUMNS = [
    "grid_name", "total_regions", "active_users_30d",
    "online_users_now", "total_users", "land_sqm", "status", "collected_at",
]


def _ensure_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)


def _v(row, col):
    """Format value for display — dash for None."""
    v = row.get(col)
    return str(v) if v is not None else "—"


def _sqm_to_km2(sqm) -> str:
    """Convert square meters to km² string."""
    if sqm is None:
        return "—"
    try:
        return f"{int(sqm) / 1_000_000:.2f} km²"
    except (ValueError, TypeError):
        return "—"


def to_csv(snapshots: list, month: str = None) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Grid Name", "Regions", "Active Users", "Online Now",
                      "Total Users", "Land (sqm)", "Status", "Collected At"])
    for s in snapshots:
        writer.writerow([s.get(c, "") for c in COLUMNS])
    return buf.getvalue()


def to_json(snapshots: list, month: str = None) -> str:
    clean = []
    for s in snapshots:
        clean.append({c: s.get(c) for c in COLUMNS})
    return json.dumps({
        "month": month,
        "generated_at": datetime.utcnow().isoformat(),
        "count": len(clean),
        "grids": clean,
    }, indent=2)


def to_markdown(snapshots: list, month: str = None) -> str:
    title = f"## OpenSim Grid Stats — {month}\n\n" if month else ""
    header = "| Grid | Regions | Active Users | Online Now | Total Users | Land |"
    sep = "|------|---------|-------------|------------|-------------|------|"
    rows = []
    for s in snapshots:
        if s.get("status") != "online":
            continue
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            _v(s, "grid_name"), _v(s, "total_regions"),
            _v(s, "active_users_30d"), _v(s, "online_users_now"),
            _v(s, "total_users"), _sqm_to_km2(s.get("land_sqm")),
        ))
    return title + header + "\n" + sep + "\n" + "\n".join(rows) + "\n"


def to_html_table(snapshots: list, month: str = None) -> str:
    title = f'<h3>OpenSim Grid Stats &mdash; {month}</h3>\n' if month else ""
    rows = ""
    for s in snapshots:
        if s.get("status") != "online":
            continue
        rows += (
            f'  <tr><td>{_v(s,"grid_name")}</td><td>{_v(s,"total_regions")}</td>'
            f'<td>{_v(s,"active_users_30d")}</td><td>{_v(s,"online_users_now")}</td>'
            f'<td>{_v(s,"total_users")}</td><td>{_sqm_to_km2(s.get("land_sqm"))}</td></tr>\n'
        )
    return f"""{title}<table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;">
<thead><tr><th>Grid</th><th>Regions</th><th>Active Users</th><th>Online Now</th><th>Total Users</th><th>Land</th></tr></thead>
<tbody>
{rows}</tbody>
</table>
"""


def export_to_file(snapshots: list, fmt: str, month: str = None) -> str:
    _ensure_dir()
    month_slug = month or datetime.utcnow().strftime("%Y-%m")
    ext_map = {"csv": "csv", "json": "json", "markdown": "md", "html": "html"}
    filename = f"grid_stats_{month_slug}.{ext_map[fmt]}"
    filepath = os.path.join(EXPORT_DIR, filename)

    fn_map = {"csv": to_csv, "json": to_json, "markdown": to_markdown, "html": to_html_table}
    with open(filepath, "w") as f:
        f.write(fn_map[fmt](snapshots, month_slug))
    return filepath
