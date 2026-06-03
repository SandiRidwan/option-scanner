import logging
import sys
import os
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Buat folder logs dan data SEBELUM logging diinisialisasi
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/main.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 50)
    logger.info("OPTIONS SCANNER BOT — STARTING UP")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    from config import (
        GROQ_API_KEY, DISCORD_WEBHOOK, DRY_RUN,
        SCAN_TIME, MIDDAY_TIME, EOD_TIME, TIMEZONE
    )

    logger.info(f"DRY_RUN: {DRY_RUN}")
    logger.info(f"TIMEZONE: {TIMEZONE}")
    logger.info(f"Schedule: Scan={SCAN_TIME} | Alert=09:31 | Midday={MIDDAY_TIME} | EOD={EOD_TIME}")
    logger.info(f"GROQ_API_KEY: {'✅ Set' if GROQ_API_KEY else '❌ Missing'}")
    logger.info(f"DISCORD_WEBHOOK: {'✅ Set' if DISCORD_WEBHOOK else '❌ Missing'}")

    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY tidak ditemukan di .env — abort.")
        sys.exit(1)

    if not DISCORD_WEBHOOK:
        logger.error("DISCORD_WEBHOOK tidak ditemukan di .env — abort.")
        sys.exit(1)

    try:
        from database import get_connection
        conn = get_connection()
        conn.close()
        logger.info("Database: ✅ Connected")
    except Exception as e:
        logger.error(f"Database connection failed: {e} — abort.")
        sys.exit(1)

    logger.info("Starting scheduler...")
    from scheduler import start_scheduler
    start_scheduler()


if __name__ == "__main__":
    main()