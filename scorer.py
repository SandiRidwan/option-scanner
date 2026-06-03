import pandas as pd
import numpy as np
import logging
import sys
import os
import json
from config import WEIGHTS, FILTERS

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scorer.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def normalize_series(series):
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series([50.0] * len(series), index=series.index)
    return ((series - min_val) / (max_val - min_val)) * 100


def calculate_delta_score(df):
    target_moneyness = 1.00
    distance_from_target = abs(df["moneyness"] - target_moneyness)
    inverted = 1 / (1 + distance_from_target * 10)
    return normalize_series(inverted)


def calculate_vol_oi_score(df):
    oi = df["openInterest"].replace(0, 1)
    vol = df["volume"].fillna(0)
    ratio = vol / oi
    ratio_capped = ratio.clip(upper=5.0)
    return normalize_series(ratio_capped)


def calculate_gamma_score(df):
    iv = df["impliedVolatility"].fillna(0)

    def iv_score(val):
        if val <= 0:
            return 0
        elif 0.30 <= val <= 0.80:
            return 1.0
        elif val < 0.30:
            return val / 0.30
        else:
            return max(0, 1.0 - (val - 0.80) / 0.80)

    iv_scores = iv.apply(iv_score)
    return normalize_series(iv_scores)


def calculate_liquidity_bonus(df):
    bonus = pd.Series(0.0, index=df.index)
    high_oi = df["openInterest"] > 1000
    high_vol = df["volume"] > 500
    tight_spread = df["spread_pct"] < 0.10
    bonus[high_oi & high_vol & tight_spread] = 10.0
    return bonus


def score_contracts(df):
    if df.empty:
        logger.error("Empty dataframe received — nothing to score")
        return pd.DataFrame()

    logger.info(f"Scoring {len(df)} contracts...")

    scored = df.copy()

    scored["delta_score"] = calculate_delta_score(scored)
    scored["vol_oi_score"] = calculate_vol_oi_score(scored)
    scored["gamma_score"] = calculate_gamma_score(scored)
    scored["liquidity_bonus"] = calculate_liquidity_bonus(scored)

    scored["composite_score"] = (
        scored["delta_score"] * WEIGHTS["delta"] +
        scored["vol_oi_score"] * WEIGHTS["vol_oi"] +
        scored["gamma_score"] * WEIGHTS["gamma"] +
        scored["liquidity_bonus"]
    ).round(2)

    scored = scored.sort_values("composite_score", ascending=False)
    scored = scored.reset_index(drop=True)

    logger.info(f"Scoring complete. Top score: {scored['composite_score'].iloc[0]:.2f}")

    return scored


def get_kill_shot(scored_df):
    if scored_df.empty:
        return None

    top = scored_df.iloc[0]

    if top["composite_score"] < 30.0:
        logger.warning(
            f"Top score {top['composite_score']:.2f} below threshold 30.0 "
            f"— no Kill Shot today"
        )
        return None

    kill_shot = {
        "ticker": top["ticker"],
        "expiry": top["expiry"],
        "strike": top["strike"],
        "option_type": top["option_type"],
        "bid": top["bid"],
        "ask": top["ask"],
        "mid_price": top["mid_price"],
        "volume": int(top["volume"]),
        "open_interest": int(top["openInterest"]),
        "implied_volatility": round(top["impliedVolatility"] * 100, 2),
        "moneyness": round(top["moneyness"], 4),
        "spread_pct": round(top["spread_pct"] * 100, 2),
        "underlying_price": round(top["underlying_price"], 2),
        "composite_score": top["composite_score"],
        "delta_score": round(top["delta_score"], 2),
        "vol_oi_score": round(top["vol_oi_score"], 2),
        "gamma_score": round(top["gamma_score"], 2),
    }

    logger.info("=" * 50)
    logger.info("KILL SHOT SELECTED:")
    logger.info(f"  Ticker    : {kill_shot['ticker']}")
    logger.info(f"  Strike    : ${kill_shot['strike']}")
    logger.info(f"  Expiry    : {kill_shot['expiry']}")
    logger.info(f"  Bid/Ask   : ${kill_shot['bid']} / ${kill_shot['ask']}")
    logger.info(f"  Volume    : {kill_shot['volume']:,}")
    logger.info(f"  OI        : {kill_shot['open_interest']:,}")
    logger.info(f"  IV        : {kill_shot['implied_volatility']}%")
    logger.info(f"  Score     : {kill_shot['composite_score']}")
    logger.info("=" * 50)

    return kill_shot


def run_scorer():
    """
    Wrapper function untuk dipanggil dari scheduler.
    Load scan_result.csv, score, save hasil, return kill_shot dict.
    """
    if not os.path.exists("data/scan_result.csv"):
        logger.error("data/scan_result.csv not found — run scanner first.")
        return None

    df = pd.read_csv("data/scan_result.csv")
    logger.info(f"Loaded {len(df)} contracts from scan_result.csv")

    scored = score_contracts(df)
    if scored.empty:
        logger.error("Scoring returned empty dataframe.")
        return None

    scored.to_csv("data/scored_contracts.csv", index=False)
    logger.info("Saved scored_contracts.csv")

    kill_shot = get_kill_shot(scored)
    if kill_shot:
        with open("data/kill_shot.json", "w", encoding="utf-8") as f:
            json.dump(kill_shot, f, indent=2)
        logger.info("Saved kill_shot.json")

    return kill_shot


if __name__ == "__main__":
    if not os.path.exists("data/scan_result.csv"):
        print("ERROR: data/scan_result.csv not found. Run scanner.py first.")
        exit(1)

    df = pd.read_csv("data/scan_result.csv")
    print(f"Loaded {len(df)} contracts from scan_result.csv")

    scored = score_contracts(df)

    if not scored.empty:
        print("\n=== TOP 10 CONTRACTS ===")
        print(scored[[
            "ticker", "strike", "expiry", "bid", "ask",
            "volume", "openInterest", "impliedVolatility",
            "composite_score", "delta_score", "vol_oi_score", "gamma_score"
        ]].head(10).to_string(index=False))

        kill_shot = get_kill_shot(scored)

        if kill_shot:
            print("\n=== KILL SHOT ===")
            for k, v in kill_shot.items():
                print(f"  {k}: {v}")

            with open("data/kill_shot.json", "w") as f:
                json.dump(kill_shot, f, indent=2)
            print("\nSaved to data/kill_shot.json")
        else:
            print("No Kill Shot today.")

        scored.to_csv("data/scored_contracts.csv", index=False)
        print("Saved to data/scored_contracts.csv")