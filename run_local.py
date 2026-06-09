import json
import logging
import sys
import os
import pandas as pd
from datetime import datetime

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/run_local.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 50)
    logger.info("LOCAL RUNNER — STARTING")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    # Step 1: Scan
    logger.info("Step 1: Running scanner...")
    from scanner import run_scanner
    scan_df = run_scanner()
    if scan_df.empty:
        logger.error("Scanner returned empty — abort.")
        return
    scan_df.to_csv("data/scan_result.csv", index=False)
    logger.info(f"Scan saved: {len(scan_df)} contracts")

    # Step 2: Score + Kill Shot
    logger.info("Step 2: Running scorer...")
    from scorer import run_scorer
    kill_shot = run_scorer()
    if not kill_shot:
        logger.error("No kill shot generated — abort.")
        return

    # Step 3: Groq AI explanation
    logger.info("Step 3: Generating AI explanation...")
    from signal_bot import generate_kill_shot_explanation
    explanation = generate_kill_shot_explanation(kill_shot)

    # Step 4: Load signal output
    with open("data/signal_output.json", encoding="utf-8") as f:
        signal_output = json.load(f)

    # Step 5: Insert ke Railway PostgreSQL
    logger.info("Step 5: Inserting to Railway PostgreSQL...")
    from database import insert_signal, upsert_daily_log
    insert_signal(kill_shot, explanation)

    scored_df = pd.read_csv("data/scored_contracts.csv")
    total_scanned = len(scored_df)
    total_tickers = scored_df["ticker"].nunique()
    top_score = float(scored_df["composite_score"].max())
    upsert_daily_log(total_scanned, total_tickers, top_score, kill_shot)

    # Step 6: Kirim Kill Shot Discord alert dari lokal
    logger.info("Step 6: Sending Kill Shot Discord alert...")
    from discord_alert import send_kill_shot_alert
    send_kill_shot_alert(signal_output)

    logger.info("=" * 50)
    logger.info("LOCAL RUNNER SELESAI")
    logger.info(f"Kill Shot: {kill_shot['ticker']} ${kill_shot['strike']} {kill_shot['option_type']} — Score: {kill_shot['composite_score']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
