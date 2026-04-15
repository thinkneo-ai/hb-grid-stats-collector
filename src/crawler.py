"""Universal OpenSim grid stats crawler.

Supports three formats with auto-detection:
  - diva_wifi  : Parses Diva Distro /wifi HTML pages
  - plaintext  : Parses plain-text grid_info (key = value or key: value)
  - json       : Parses JSON API response
  - auto       : Tries JSON → plaintext → diva_wifi
"""

import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)

TIMEOUT = 30
HEADERS = {
    "User-Agent": "HBGridStatsCollector/1.0 (+https://github.com/thinkneo-ai/hb-grid-stats-collector)"
}

# Canonical field names
STAT_FIELDS = ["total_regions", "active_users_30d", "online_users_now", "total_users", "land_sqm"]


def crawl_grid(name: str, url: str, fmt: str = "auto") -> dict:
    """Crawl a single grid and return normalized stats dict."""
    result = {
        "grid_name": name,
        "url": url,
        "total_regions": None,
        "active_users_30d": None,
        "online_users_now": None,
        "total_users": None,
        "land_sqm": None,
        "status": "error",
        "error_msg": None,
    }

    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS, verify=False)
        resp.raise_for_status()
        content = resp.text.strip()
    except requests.RequestException as e:
        result["error_msg"] = str(e)[:500]
        logger.error("Fetch failed — %s (%s): %s", name, url, e)
        return result

    if not content:
        result["error_msg"] = "Empty response"
        return result

    try:
        if fmt == "json":
            parsed = _parse_json(content)
        elif fmt == "plaintext":
            parsed = _parse_plaintext(content)
        elif fmt == "diva_wifi":
            parsed = _parse_diva_wifi(content)
        else:  # auto
            parsed = _try_auto(content)

        result.update(parsed)
        result["status"] = "online"
    except Exception as e:
        result["error_msg"] = f"Parse error: {e}"
        logger.error("Parse error — %s: %s", name, e)

    return result


# ── Auto-detect ──────────────────────────────────────────────────────────

def _try_auto(content: str) -> dict:
    """Auto-detect format: JSON → plaintext → Diva WiFi HTML."""
    # Try JSON
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return _parse_json(content)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try plaintext (grid_info)
    if _looks_like_plaintext(content):
        return _parse_plaintext(content)

    # Fallback: HTML (Diva WiFi)
    return _parse_diva_wifi(content)


def _looks_like_plaintext(content: str) -> bool:
    lines = content.strip().split("\n")
    if len(lines) < 2:
        return False
    kv_lines = sum(1 for l in lines[:20] if re.match(r"^[\w\s._-]+\s*[=:]\s*.+", l))
    html_tags = sum(1 for l in lines[:20] if re.search(r"<\w+[\s>]", l))
    return kv_lines >= 2 and html_tags == 0


# ── JSON parser ──────────────────────────────────────────────────────────

def _parse_json(content: str) -> dict:
    data = json.loads(content)
    return _normalize(data)


# ── Plaintext parser ────────────────────────────────────────────────────

def _parse_plaintext(content: str) -> dict:
    kv = {}
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([\w\s._-]+?)\s*[=:]\s*(.+)$", line)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
            val = m.group(2).strip()
            kv[key] = val
    return _normalize(kv)


# ── Diva WiFi HTML parser ───────────────────────────────────────────────

def _parse_diva_wifi(content: str) -> dict:
    soup = BeautifulSoup(content, "lxml")
    text = soup.get_text(separator="\n")
    kv = {}

    # Regex patterns for stats commonly found in WiFi pages
    patterns = [
        (r"(?:total\s+)?regions?\s*[:\-=]\s*(\d[\d,]*)", "total_regions"),
        (r"(?:online\s+(?:users?|now)|users?\s+online|online\s+now)\s*[:\-=]\s*(\d[\d,]*)", "online_users_now"),
        (r"active\s+users?\s*(?:\(?\s*30\s*d(?:ays?)?\s*\)?)?\s*[:\-=]\s*(\d[\d,]*)", "active_users_30d"),
        (r"(?:total\s+)?(?:registered\s+)?users?\s*[:\-=]\s*(\d[\d,]*)", "total_users"),
        (r"(?:total\s+)?(?:land|area)\s*(?:\(?\s*sq\.?\s*m\s*\)?)?\s*[:\-=]\s*(\d[\d,]*)", "land_sqm"),
    ]
    for pat, field in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            kv[field] = m.group(1).replace(",", "")

    # Also parse tables
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).lower()
                val = cells[1].get_text(strip=True).replace(",", "")
                if "region" in key:
                    kv.setdefault("total_regions", val)
                elif "online" in key:
                    kv.setdefault("online_users_now", val)
                elif "active" in key:
                    kv.setdefault("active_users_30d", val)
                elif "user" in key or "account" in key:
                    kv.setdefault("total_users", val)

    # Parse stat spans/divs
    for el in soup.find_all(["span", "div", "p"], class_=re.compile(r"stat|count|metric", re.I)):
        txt = el.get_text(strip=True).lower()
        m_num = re.search(r"(\d[\d,]*)", txt)
        if m_num:
            num = m_num.group(1).replace(",", "")
            if "region" in txt:
                kv.setdefault("total_regions", num)
            elif "online" in txt:
                kv.setdefault("online_users_now", num)

    return _normalize(kv)


# ── Field normalizer ────────────────────────────────────────────────────

_FIELD_MAP = {
    "regions": "total_regions", "total_regions": "total_regions",
    "totalregions": "total_regions", "region_count": "total_regions",
    "regioncount": "total_regions", "num_regions": "total_regions",
    "active_users": "active_users_30d", "active_users_30d": "active_users_30d",
    "activeusers30d": "active_users_30d", "active_users_last_30_days": "active_users_30d",
    "active30d": "active_users_30d", "monthly_active_users": "active_users_30d",
    "online_users": "online_users_now", "online_users_now": "online_users_now",
    "onlineusers": "online_users_now", "users_online": "online_users_now",
    "online_now": "online_users_now", "online": "online_users_now",
    "total_users": "total_users", "totalusers": "total_users",
    "users": "total_users", "user_count": "total_users",
    "registered_users": "total_users", "accounts": "total_users",
    "land_sqm": "land_sqm", "land_area": "land_sqm",
    "total_land": "land_sqm", "land": "land_sqm", "area_sqm": "land_sqm",
}


def _normalize(raw: dict) -> dict:
    out = {}
    for key, val in raw.items():
        canonical = key.lower().strip().replace(" ", "_").replace("-", "_")
        field = _FIELD_MAP.get(canonical)
        if field:
            out[field] = _to_int(val)
    return out


def _to_int(val) -> int | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    try:
        return int(str(val).replace(",", "").replace(" ", "").strip())
    except (ValueError, TypeError):
        return None
