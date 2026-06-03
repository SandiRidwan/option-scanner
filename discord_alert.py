import json
import logging
import sys
import os
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed
from config import DISCORD_WEBHOOK, DRY_RUN

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/discord_alert.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def send_kill_shot_alert(signal_output: dict) -> bool:
    """
    Kirim Kill Shot alert ke Discord — jam 9:31 AM ET.
    signal_output = isi dari data/signal_output.json
    """
    if DRY_RUN:
        logger.info("[DRY RUN] send_kill_shot_alert() dipanggil — tidak dikirim ke Discord.")
        logger.info(f"[DRY RUN] Preview: {signal_output['ticker']} ${signal_output['strike']} {signal_output['option_type']} | Score: {signal_output['composite_score']}")
        return True

    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK)

        embed = DiscordEmbed(
            title=f"🎯 KILL SHOT — {signal_output['ticker']} ${signal_output['strike']} {signal_output['option_type']}",
            description=signal_output["explanation"],
            color="FF4500"
        )

        embed.add_embed_field(name="📅 Expiry", value=signal_output["expiry"], inline=True)
        embed.add_embed_field(name="🏆 Score", value=f"{signal_output['composite_score']}/110", inline=True)
        embed.add_embed_field(name="⏰ Signal Time", value="9:31 AM ET", inline=True)
        embed.set_footer(text="Options Scanner Bot | Data: yfinance (15min delay) | NOT financial advice")
        embed.set_timestamp()

        webhook.add_embed(embed)
        response = webhook.execute()

        if response.status_code in (200, 204):
            logger.info(f"Kill Shot alert sent: {signal_output['ticker']} ${signal_output['strike']} {signal_output['option_type']}")
            return True
        else:
            logger.error(f"Discord error: {response.status_code} — {response.text}")
            return False

    except Exception as e:
        logger.error(f"send_kill_shot_alert() failed: {e}")
        return False


def send_midday_update(signal_output: dict, top_contracts: list) -> bool:
    """
    Kirim midday update ke Discord — jam 12:00 PM ET.
    top_contracts = list of dict dari scored_contracts.csv (top 5)
    """
    if DRY_RUN:
        logger.info("[DRY RUN] send_midday_update() dipanggil — tidak dikirim ke Discord.")
        return True

    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK)

        embed = DiscordEmbed(
            title="📊 MIDDAY UPDATE — Top Contracts Right Now",
            description=f"Kill Shot tetap: **{signal_output['ticker']} ${signal_output['strike']} {signal_output['option_type']}** (Score: {signal_output['composite_score']}/110)",
            color="1E90FF"
        )

        top_text = ""
        for i, c in enumerate(top_contracts[:5], 1):
            top_text += f"`{i}.` **{c['ticker']}** ${c['strike']} {c['option_type']} — Score: {c['composite_score']:.1f}\n"

        embed.add_embed_field(name="🔥 Top 5 Contracts", value=top_text, inline=False)
        embed.add_embed_field(name="⏰ Update Time", value="12:00 PM ET", inline=True)
        embed.set_footer(text="Options Scanner Bot | Data: yfinance (15min delay) | NOT financial advice")
        embed.set_timestamp()

        webhook.add_embed(embed)
        response = webhook.execute()

        if response.status_code in (200, 204):
            logger.info("Midday update sent.")
            return True
        else:
            logger.error(f"Discord error: {response.status_code} — {response.text}")
            return False

    except Exception as e:
        logger.error(f"send_midday_update() failed: {e}")
        return False


def send_eod_recap(signal_output: dict, total_scanned: int, top_score: float) -> bool:
    """
    Kirim end-of-day recap ke Discord — jam 3:45 PM ET.
    total_scanned = jumlah contracts yang di-scan hari ini
    top_score = composite score tertinggi hari ini
    """
    if DRY_RUN:
        logger.info("[DRY RUN] send_eod_recap() dipanggil — tidak dikirim ke Discord.")
        return True

    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK)

        today = datetime.now().strftime("%A, %B %d %Y")

        embed = DiscordEmbed(
            title=f"📋 EOD RECAP — {today}",
            description=f"Market closed. Kill Shot hari ini: **{signal_output['ticker']} ${signal_output['strike']} {signal_output['option_type']}**",
            color="2ECC71"
        )

        embed.add_embed_field(name="🔍 Contracts Scanned", value=f"{total_scanned:,}", inline=True)
        embed.add_embed_field(name="🏆 Top Score", value=f"{top_score}/110", inline=True)
        embed.add_embed_field(name="🎯 Kill Shot", value=f"{signal_output['ticker']} ${signal_output['strike']} {signal_output['option_type']}", inline=True)
        embed.add_embed_field(name="⏰ EOD Time", value="3:45 PM ET", inline=True)
        embed.set_footer(text="Options Scanner Bot | Data: yfinance (15min delay) | NOT financial advice")
        embed.set_timestamp()

        webhook.add_embed(embed)
        response = webhook.execute()

        if response.status_code in (200, 204):
            logger.info("EOD recap sent.")
            return True
        else:
            logger.error(f"Discord error: {response.status_code} — {response.text}")
            return False

    except Exception as e:
        logger.error(f"send_eod_recap() failed: {e}")
        return False