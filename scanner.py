import yfinance as yf
import pandas as pd
import logging
import time
import sys
from datetime import datetime, date
from config import TICKER_UNIVERSE, FILTERS

# Fix encoding untuk Windows Command Prompt
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scanner.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_nearest_expiry(ticker_obj):
    """
    Ambil expiry date terdekat yang masih 0DTE atau 1-7 hari ke depan.
    Teknik advance: filter expiry yang terlalu jauh karena liquidity
    options menurun drastis semakin jauh expiry-nya.
    """
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


def fetch_options_chain(ticker_symbol, expiry):
    """
    Ambil options chain (calls) untuk satu ticker.
    Fokus CALLS untuk 0DTE scanner.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
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
    """
    Filter kontrak berdasarkan minimum liquidity.
    Kombinasi OI + Volume + Bid-Ask spread.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    filtered = df.copy()

    filtered = filtered[
        filtered["openInterest"] >= FILTERS["min_open_interest"]
    ]

    filtered["volume"] = filtered["volume"].fillna(0)
    filtered = filtered[filtered["volume"] >= FILTERS["min_volume"]]

    filtered = filtered[filtered["bid"] > 0]
    filtered = filtered[filtered["ask"] > 0]

    filtered["mid_price"] = (filtered["bid"] + filtered["ask"]) / 2
    filtered["spread_pct"] = (
        filtered["ask"] - filtered["bid"]
    ) / filtered["mid_price"]
    filtered = filtered[filtered["spread_pct"] <= 0.50]

    filtered = filtered[
        (filtered["moneyness"] >= 0.85) &
        (filtered["moneyness"] <= 1.15)
    ]

    return filtered


def run_scanner():
    """
    Main scanner function.
    Loop semua ticker, ambil data, filter, return dataframe bersih.
    """
    logger.info("=" * 50)
    logger.info(f"Scanner started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Scanning {len(TICKER_UNIVERSE)} tickers...")

    all_contracts = []
    failed_tickers = []
    scanned = 0

    for ticker_symbol in TICKER_UNIVERSE:
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            expiry = get_nearest_expiry(ticker_obj)

            if not expiry:
                logger.debug(f"{ticker_symbol}: no valid expiry found, skipping")
                continue

            chain = fetch_options_chain(ticker_symbol, expiry)
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
