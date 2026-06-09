import logging
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/database.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def _cast(val):
    """Cast numpy types ke Python native type agar kompatibel dengan psycopg2."""
    if hasattr(val, 'item'):
        return val.item()
    return val


def insert_signal(kill_shot: dict, explanation: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO signals (
                ticker, strike, expiry, option_type,
                composite_score, delta_score, vol_oi_score, gamma_score,
                underlying_price, bid, ask, mid_price,
                volume, open_interest, implied_volatility, explanation
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            _cast(kill_shot["ticker"]),
            _cast(kill_shot["strike"]),
            _cast(kill_shot["expiry"]),
            _cast(kill_shot["option_type"]),
            _cast(kill_shot["composite_score"]),
            _cast(kill_shot["delta_score"]),
            _cast(kill_shot["vol_oi_score"]),
            _cast(kill_shot["gamma_score"]),
            _cast(kill_shot["underlying_price"]),
            _cast(kill_shot["bid"]),
            _cast(kill_shot["ask"]),
            _cast(kill_shot["mid_price"]),
            _cast(kill_shot["volume"]),
            _cast(kill_shot["open_interest"]),
            _cast(kill_shot["implied_volatility"]),
            explanation
        ))

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Signal inserted: {kill_shot['ticker']} ${kill_shot['strike']} {kill_shot['option_type']}")
        return True

    except Exception as e:
        logger.error(f"insert_signal() failed: {e}")
        return False


def upsert_daily_log(total_scanned: int, total_tickers: int, top_score: float, kill_shot: dict) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO daily_log (
                log_date, total_contracts_scanned, total_tickers_scanned,
                top_score, kill_shot_ticker, kill_shot_strike, kill_shot_type,
                scan_completed_at, alerts_sent
            ) VALUES (
                CURRENT_DATE, %s, %s, %s, %s, %s, %s, NOW(), 0
            )
            ON CONFLICT (log_date) DO UPDATE SET
                total_contracts_scanned = EXCLUDED.total_contracts_scanned,
                total_tickers_scanned = EXCLUDED.total_tickers_scanned,
                top_score = EXCLUDED.top_score,
                kill_shot_ticker = EXCLUDED.kill_shot_ticker,
                kill_shot_strike = EXCLUDED.kill_shot_strike,
                kill_shot_type = EXCLUDED.kill_shot_type,
                scan_completed_at = NOW()
        """, (
            int(total_scanned),
            int(total_tickers),
            float(top_score),
            _cast(kill_shot["ticker"]),
            _cast(kill_shot["strike"]),
            _cast(kill_shot["option_type"])
        ))

        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Daily log upserted: {total_scanned} contracts, top score {top_score}")
        return True

    except Exception as e:
        logger.error(f"upsert_daily_log() failed: {e}")
        return False


def increment_alerts_sent() -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE daily_log
            SET alerts_sent = alerts_sent + 1
            WHERE log_date = CURRENT_DATE
        """)

        conn.commit()
        cur.close()
        conn.close()
        logger.info("alerts_sent incremented.")
        return True

    except Exception as e:
        logger.error(f"increment_alerts_sent() failed: {e}")
        return False


def get_latest_signal() -> dict:
    """
    Ambil signal terbaru hari ini dari DB.
    Return dict atau None kalau tidak ada.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT ticker, strike, expiry::text, option_type,
                   composite_score, delta_score, vol_oi_score, gamma_score,
                   underlying_price, bid, ask, mid_price,
                   volume, open_interest, implied_volatility, explanation
            FROM signals
            WHERE DATE(created_at) = CURRENT_DATE
            ORDER BY composite_score DESC
            LIMIT 1
        """)

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            logger.warning("No signal found in DB for today.")
            return None

        result = dict(row)
        result["strike"] = float(result["strike"])
        result["composite_score"] = float(result["composite_score"])
        logger.info(f"Loaded signal from DB: {result['ticker']} ${result['strike']} {result['option_type']}")
        return result

    except Exception as e:
        logger.error(f"get_latest_signal() failed: {e}")
        return None


def get_latest_daily_log() -> dict:
    """
    Ambil daily log hari ini dari DB.
    Return dict atau None kalau tidak ada.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT *
            FROM daily_log
            WHERE log_date = CURRENT_DATE
            LIMIT 1
        """)

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            logger.warning("No daily log found for today.")
            return None

        result = dict(row)
        result["top_score"] = float(result["top_score"])
        result["kill_shot_strike"] = float(result["kill_shot_strike"])
        return result

    except Exception as e:
        logger.error(f"get_latest_daily_log() failed: {e}")
        return None