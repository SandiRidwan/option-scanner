import logging
import sys
import json
import os
import pandas as pd
from datetime import datetime
import pandas_market_calendars as mcal
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import SCAN_TIME, MIDDAY_TIME, EOD_TIME, TIMEZONE
from discord_alert import send_kill_shot_alert, send_midday_update, send_eod_recap
from database import increment_alerts_sent, get_latest_signal, get_latest_daily_log

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")
nyse = mcal.get_calendar("NYSE")


def is_market_open_today() -> bool:
    today = datetime.now(ET).strftime("%Y-%m-%d")
    schedule = nyse.schedule(start_date=today, end_date=today)
    return not schedule.empty


def job_kill_shot_alert():
    """9:31 AM ET — Kirim Kill Shot alert ke Discord (load dari DB)."""
    if not is_market_open_today():
        logger.info("Market tutup hari ini — kill shot alert dilewati.")
        return

    try:
        signal = get_latest_signal()
        if not signal:
            logger.warning("No signal in DB today — skip kill shot alert.")
            return

        success = send_kill_shot_alert(signal)
        if success:
            increment_alerts_sent()
            logger.info(f"Kill Shot alert sent: {signal['ticker']} ${signal['strike']} {signal['option_type']}")

    except Exception as e:
        logger.error(f"job_kill_shot_alert() failed: {e}")


def job_midday_update():
    """12:00 PM ET — Kirim midday update ke Discord (load dari DB)."""
    if not is_market_open_today():
        logger.info("Market tutup hari ini — midday update dilewati.")
        return

    try:
        signal = get_latest_signal()
        if not signal:
            logger.warning("No signal in DB today — skip midday update.")
            return

        daily = get_latest_daily_log()
        top_contracts = []
        if daily:
            top_contracts = [{
                "ticker": daily["kill_shot_ticker"],
                "strike": daily["kill_shot_strike"],
                "option_type": daily["kill_shot_type"],
                "composite_score": daily["top_score"]
            }]

        success = send_midday_update(signal, top_contracts)
        if success:
            increment_alerts_sent()
            logger.info("Midday update sent.")

    except Exception as e:
        logger.error(f"job_midday_update() failed: {e}")


def job_eod_recap():
    """3:45 PM ET — Kirim EOD recap ke Discord (load dari DB)."""
    if not is_market_open_today():
        logger.info("Market tutup hari ini — EOD recap dilewati.")
        return

    try:
        signal = get_latest_signal()
        if not signal:
            logger.warning("No signal in DB today — skip EOD recap.")
            return

        daily = get_latest_daily_log()
        total_scanned = daily["total_contracts_scanned"] if daily else 0
        top_score = daily["top_score"] if daily else signal["composite_score"]

        success = send_eod_recap(signal, total_scanned, top_score)
        if success:
            increment_alerts_sent()
            logger.info("EOD recap sent.")

    except Exception as e:
        logger.error(f"job_eod_recap() failed: {e}")


def start_scheduler():
    """Start APScheduler — hanya Midday dan EOD (Morning Scan jalan di lokal)."""
    scheduler = BlockingScheduler(timezone=ET)

    mid_h, mid_m = MIDDAY_TIME.split(":")
    eod_h, eod_m = EOD_TIME.split(":")

    scheduler.add_job(
        job_kill_shot_alert,
        CronTrigger(hour="09", minute="31", timezone=ET),
        id="kill_shot_alert",
        name="Kill Shot Alert 9:31 AM ET"
    )
    scheduler.add_job(
        job_midday_update,
        CronTrigger(hour=mid_h, minute=mid_m, timezone=ET),
        id="midday_update",
        name="Midday Update 12:00 PM ET"
    )
    scheduler.add_job(
        job_eod_recap,
        CronTrigger(hour=eod_h, minute=eod_m, timezone=ET),
        id="eod_recap",
        name="EOD Recap 3:45 PM ET"
    )

    logger.info("Scheduler started. Jobs terdaftar:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}")

    scheduler.start()