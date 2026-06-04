import logging
import sys
import json
import pandas as pd
from datetime import datetime
import pandas_market_calendars as mcal
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import SCAN_TIME, MIDDAY_TIME, EOD_TIME, TIMEZONE
from scanner i
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
    """Cek apakah NYSE buka hari ini."""
    today = datetime.now(ET).strftime("%Y-%m-%d")
    schedule = nyse.schedule(start_date=today, end_date=today)
    return not schedule.empty


def job_morning_scan():
    """9:25 AM ET — Scan, score, generate AI explanation, simpan ke DB."""
    if not is_market_open_today():
        logger.info("Market tutup hari ini — morning scan dilewati.")
        return

    logger.info("=== MORNING SCAN DIMULAI ===")

    try:
        # Step 1: Scan
        logger.info("Menjalankan scanner...")
        scan_df = run_scanner()
        if scan_df.empty:
            logger.error("Scanner returned empty — abort morning scan.")
            return
        scan_df.to_csv("data/scan_result.csv", index=False)
        logger.info(f"Scan result saved: {len(scan_df)} contracts")

        # Step 2: Score
        logger.info("Menjalankan scorer...")
        kill_shot = run_scorer()
        if not kill_shot:
            logger.error("No kill shot generated — abort.")
            return

        # Step 3: Generate AI explanation
        explanation = generate_kill_shot_explanation(kill_shot)

        # Step 4: Load signal output
        with open("data/signal_output.json", encoding="utf-8") as f:
            signal_output = json.load(f)

        # Step 5: Insert ke DB
        insert_signal(kill_shot, explanation)

        # Step 6: Upsert daily log
        scored_df = pd.read_csv("data/scored_contracts.csv")
        total_scanned = len(scored_df)
        total_tickers = scored_df["ticker"].nunique()
        top_score = float(scored_df["composite_score"].max())
        upsert_daily_log(total_scanned, total_tickers, top_score, kill_shot)

        logger.info("=== MORNING SCAN SELESAI ===")

    except Exception as e:
        logger.error(f"job_morning_scan() failed: {e}")


def job_kill_shot_alert():
    """9:31 AM ET — Kirim Kill Shot alert ke Discord."""
    if not is_market_open_today():
        logger.info("Market tutup hari ini — kill shot alert dilewati.")
        return

    try:
        with open("data/signal_output.json", encoding="utf-8") as f:
            signal_output = json.load(f)

        success = send_kill_shot_alert(signal_output)
        if success:
            increment_alerts_sent()

    except Exception as e:
        logger.error(f"job_kill_shot_alert() failed: {e}")


def job_midday_update():
    """12:00 PM ET — Kirim midday update ke Discord."""
    if not is_market_open_today():
        logger.info("Market tutup hari ini — midday update dilewati.")
        return

    try:
        with open("data/signal_output.json", encoding="utf-8") as f:
            signal_output = json.load(f)

        scored_df = pd.read_csv("data/scored_contracts.csv")
        top_contracts = scored_df.nlargest(5, "composite_score").to_dict("records")

        success = send_midday_update(signal_output, top_contracts)
        if success:
            increment_alerts_sent()

    except Exception as e:
        logger.error(f"job_midday_update() failed: {e}")


def job_eod_recap():
    """3:45 PM ET — Kirim EOD recap ke Discord."""
    if not is_market_open_today():
        logger.info("Market tutup hari ini — EOD recap dilewati.")
        return

    try:
        with open("data/signal_output.json", encoding="utf-8") as f:
            signal_output = json.load(f)

        scored_df = pd.read_csv("data/scored_contracts.csv")
        total_scanned = len(scored_df)
        top_score = float(scored_df["composite_score"].max())

        success = send_eod_recap(signal_output, total_scanned, top_score)
        if success:
            increment_alerts_sent()

    except Exception as e:
        logger.error(f"job_eod_recap() failed: {e}")


def start_scheduler():
    """Start APScheduler dengan semua jobs."""
    scheduler = BlockingScheduler(timezone=ET)

    scan_h, scan_m = SCAN_TIME.split(":")
    mid_h, mid_m = MIDDAY_TIME.split(":")
    eod_h, eod_m = EOD_TIME.split(":")

    scheduler.add_job(
        job_morning_scan,
        CronTrigger(hour=scan_h, minute=scan_m, timezone=ET),
        id="morning_scan",
        name="Morning Scan 9:25 AM ET"
    )
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