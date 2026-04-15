"""Orchestrates collection across all enabled grids."""

import logging
from datetime import datetime
from .database import get_enabled_grids, save_snapshot, log_collection_start, log_collection_end
from .crawler import crawl_grid

logger = logging.getLogger(__name__)


def collect_all(trigger: str = "manual") -> dict:
    """Run collection for all enabled grids. Returns summary dict."""
    grids = get_enabled_grids()
    logger.info("Starting collection — %d grids (%s)", len(grids), trigger)
    log_id = log_collection_start(trigger)

    results = []
    for g in grids:
        logger.info("  Collecting: %s", g["name"])
        data = crawl_grid(g["name"], g["url"], g["format"])
        save_snapshot(g["id"], data)
        results.append(data)

        if data["status"] == "online":
            logger.info("    OK — regions=%s users=%s",
                        data.get("total_regions", "?"), data.get("total_users", "?"))
        else:
            logger.warning("    FAIL — %s", data.get("error_msg", "unknown"))

    online = sum(1 for r in results if r["status"] == "online")
    log_collection_end(log_id, len(results), online)
    logger.info("Collection done — %d/%d online", online, len(results))

    return {
        "total": len(results),
        "online": online,
        "errors": len(results) - online,
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }
