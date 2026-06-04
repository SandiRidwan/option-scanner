import yfinance as yf
import pandas as pd
import logging
import time
import sys
import requests
from datetime import datetime, date
from config import TICKER_UNIVERSE, FILTERS

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scanner.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def get_yf_session():
    """Buat requests session dengan custom headers untuk bypass throttling."""
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_nearest_expiry(ticker_obj):
    try:
        expirations = ticker_obj.options
        if not expirations:
            return None

        today = date.today()
        valid_expiries = []

        for exp in expirations:
            exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            days_to_exp = (exp_date - today).days
            if 0 <= days_to_exp <= 7:
                valid_expiries.append(exp)

        if not valid_expiries:
            return expirations[0]

        return valid_expiries[0]

    except Exception as e:
        logger.debug(f"Error getting expiry: {e}")
        return None


def fetch_options_chain(ticker_symbol, expiry, session=None):
    try:
        ticker = yf.Ticker(ticker_symbol, session=session)
        chain = ticker.option_chain(expiry)
        calls = chain.calls.copy()

        calls["ticker"] = ticker_symbol
        calls["expiry"] = expiry
        calls["option_type"] = "CALL"

        hist = ticker.history(period="1d")
        if hist.empty:
            return None

        current_price = hist["Close"].iloc[-1]
        calls["underlying_price"] = current_price
        calls["moneyness"] = calls["strike"] / current_price

        return calls

    except Exception as e:
        logger.debug(f"Error fetching chain for {ticker_symbol}: {e}")
        return None


def apply_liquidity_filter(df):
    if df is None or df.empty:
        return pd.DataFrame()

    filtered = df.copy()
    filtered = filtered[filtered["openInterest"] >= FILTERS["min_open_interest"]]
    filtered["volume"] = filtered["volume"].fillna(0)
    filtered = filtered[filtered["volume"] >= FILTERS["min_volume"]]
    filtered = filtered[filtered["bid"] > 0]
    filtered = filtered[filtered["ask"] > 0]

    filtered["mid_price"] = (filtered["bid"] + filtered["ask"]) / 2
    filtered["spread_pct"] = (filtered["ask"] - filtered["bid"]) / filtered["mid_price"]
    filtered = filtered[filtered["spread_pct"] <= 0.50]
    filtered = filtered[
        (filtered["moneyness"] >= 0.85) &
        (filtered["moneyness"] <= 1.15)
    ]

    return filtered


def _run_scanner_once(session=None):
    """Single scan attempt — return DataFrame atau empty."""
    logger.info("=" * 50)
    logger.info(f"Scanner started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Scanning {len(TICKER_UNIVERSE)} tickers...")

    all_contracts = []
    failed_tickers = []
    scanned = 0

    for ticker_symbol in TICKER_UNIVERSE:
        try:
            ticker_obj = yf.Ticker(ticker_symbol, session=session)
            expiry = get_nearest_expiry(ticker_obj)

            if not expiry:
                logger.debug(f"{ticker_symbol}: no valid expiry found, skipping")
                continue

            chain = fetch_options_chain(ticker_symbol, expiry, session=session)
            filtered = apply_liquidity_filter(chain)

            if not filtered.empty:
                all_contracts.append(filtered)
                logger.info(
                    f"[OK] {ticker_symbol} | expiry: {expiry} | "
                    f"contracts: {len(filtered)}"
                )

            scanned += 1
            time.sleep(0.5)

        except Exception as e:
            failed_tickers.append(ticker_symbol)
            logger.warning(f"[FAIL] {ticker_symbol}: {e}")
            continue

    if not all_contracts:
        logger.error("No contracts found. Market might be closed or all tickers failed.")
        return pd.DataFrame()

    result = pd.concat(all_contracts, ignore_index=True)

    logger.info("-" * 50)
    logger.info(f"Scan complete: {scanned} tickers scanned")
    logger.info(f"Total contracts after filter: {len(result)}")
    logger.info(f"Failed tickers: {len(failed_tickers)}")
    if failed_tickers:
        logger.info(f"Failed: {', '.join(failed_tickers)}")

    return result


def run_scanner():
    """
    Main scanner dengan retry logic + custom session.
    3 attempts dengan delay 60s antar attempt.
    Fallback ke cached scan_result.csv kalau semua gagal.
    """
    import os
    session = get_yf_session()

    for attempt in range(1, 4):
        logger.info(f"Scan attempt {attempt}/3...")
        result = _run_scanner_once(session=session)

        if not result.empty:
            logger.info(f"Scan successful on attempt {attempt}.")
            return result

        if attempt < 3:
            logger.warning(f"Attempt {attempt} returned empty — retry in 60s...")
            time.sleep(60)

    # Semua retry gagal — coba fallback ke cache
    logger.error("All 3 scan attempts failed.")

    cache_path = "data/scan_result.csv"
    if os.path.exists(cache_path):
        logger.warning("Falling back to cached scan_result.csv from previous run.")
        df = pd.read_csv(cache_path)
        logger.warning(f"Loaded {len(df)} contracts from cache.")
        return df

    logger.error("No cache available. Aborting.")
    return pd.DataFrame()


if __name__ == "__main__":
    df = run_scanner()
    if not df.empty:
        print("\n=== SAMPLE OUTPUT (5 kontrak pertama) ===")
        print(df[["ticker", "expiry", "strike", "bid", "ask",
                   "volume", "openInterest", "impliedVolatility",
                   "moneyness"]].head())
        print(f"\nTotal contracts: {len(df)}")
        df.to_csv("data/scan_result.csv", index=False)
        print("Saved to data/scan_result.csv")
    else:
        print("No contracts found.")