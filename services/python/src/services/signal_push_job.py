"""Signal push job: daily factor brief generation + multi-channel notification.
Designed to be called by SchedulerEngine as a cron job (weekday 15:30).
"""
from __future__ import annotations

import json as _json
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def run_signal_push(target_date: Optional[date] = None) -> Dict:
    """Main entry point for the daily signal push job.

    Flow:
    1. Compute factor values via SignalBriefGenerator.
    2. Compute cross-sectional IC and select top factors.
    3. Render a Markdown brief.
    4. Query users with push channels configured.
    5. Push the brief through each user's configured channels.

    Args:
        target_date: Date for factor computation (defaults to today).

    Returns:
        Dict with summary: ``{date, factors_count, channels_used, users_notified, errors}``.
    """
    from src.services.signal_brief import SignalBriefGenerator
    from src.notify.channels import Alert, send_alert

    if target_date is None:
        target_date = date.today()

    result: Dict[str, Any] = {
        "date": target_date.isoformat(),
        "factors_count": 0,
        "channels_used": [],
        "users_notified": 0,
        "errors": [],
    }

    # ── Step 1: Generate signal brief ──────────────────────────────────────
    try:
        gen = SignalBriefGenerator()
        factor_values = gen.compute_daily_factors(target_date)

        if not factor_values:
            logger.warning(
                "No factor values computed for %s, skipping push", target_date
            )
            result["errors"].append("no_factor_data")
            return result

        # Compute IC.  In production forward_returns come from a market-data
        # service; for the MVP we pass an empty DataFrame and produce a
        # minimal brief (the job is still useful for plumbing verification).
        import pandas as pd

        forward_returns = pd.DataFrame()
        ics = gen.compute_cross_sectional_ic(factor_values, forward_returns)

        top_factors: List[Tuple[str, float]] = gen.select_top_factors(ics)
        result["factors_count"] = len(top_factors)

        brief: str = gen.render_markdown(top_factors, target_date=target_date)

    except Exception as exc:
        logger.error("Failed to generate signal brief: %s", exc)
        result["errors"].append(f"brief_generation_failed: {exc}")
        return result

    # ── Step 2: Find subscribers ───────────────────────────────────────────
    subscribers = _get_subscribers()
    if not subscribers:
        logger.info("No users with signal push enabled, skipping notification")
        return result

    # ── Step 3: Push to each user's channels ───────────────────────────────
    for user_id, channels in subscribers.items():
        if not channels:
            continue

        # Convert {channel_type: config} → [{type: channel_type, ...config}]
        channel_configs: List[Dict[str, Any]] = []
        for ch_type, ch_config in channels.items():
            cfg = dict(ch_config)
            cfg["type"] = ch_type
            channel_configs.append(cfg)

        alert = Alert(
            title=f"AStockPursue 每日信号 - {target_date}",
            body=brief,
            level="signal",
            source="strategy",
        )

        try:
            send_alert(alert, channel_configs)
            for ch_type in channels:
                if ch_type not in result["channels_used"]:
                    result["channels_used"].append(ch_type)
        except Exception as exc:
            err_msg = f"Failed to push to user={user_id}: {exc}"
            logger.warning(err_msg)
            result["errors"].append(err_msg)
            continue

        result["users_notified"] += 1

    logger.info("Signal push completed: %s", result)
    return result


def _get_subscribers() -> Dict[int, Dict[str, Dict[str, Any]]]:
    """Query user_settings table for users with push channels configured.

    Returns:
        Dict mapping ``user_id`` → ``{channel_type: channel_config}``,
        e.g. ``{1: {"telegram": {"chat_id": "123"}, "email": {"to": "a@b.com"}}}``.
        Returns an empty dict when the table is absent or no users are configured.
    """
    try:
        from src.db.pool import init_pool, get_connection

        init_pool()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, push_channels
                    FROM user_settings
                    WHERE signal_push_enabled = true
                    """
                )
                rows = cur.fetchall()

        # postgresql cursor
        result: Dict[int, Dict[str, Dict[str, Any]]] = {}
        for (user_id, raw_channels) in rows:
            channels: Dict[str, Dict[str, Any]]
            if isinstance(raw_channels, dict):
                channels = raw_channels
            elif isinstance(raw_channels, str):
                channels = _json.loads(raw_channels)
            else:
                channels = {}
            if channels:
                result[int(user_id)] = channels
        return result

    except ImportError:
        logger.warning("DB pool module not available, returning empty subscribers")
        return {}
    except Exception:
        # Table may not exist yet — not a fatal error for the job.
        logger.warning(
            "Error querying subscribers (user_settings table may not exist yet)",
            exc_info=True,
        )
        return {}
