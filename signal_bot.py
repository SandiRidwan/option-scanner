import json
import logging
import sys
import os
from groq import Groq
from config import GROQ_API_KEY

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/signal_bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)

def generate_kill_shot_explanation(kill_shot: dict) -> str:
    prompt = f"""You are an elite options trading analyst. Analyze this 0DTE options contract and write a concise, high-conviction signal alert.

CONTRACT DATA:
- Ticker: {kill_shot['ticker']}
- Strike: ${kill_shot['strike']}
- Expiry: {kill_shot['expiry']}
- Type: {kill_shot['option_type']}
- Underlying Price: ${kill_shot['underlying_price']}
- Bid/Ask: ${kill_shot['bid']} / ${kill_shot['ask']}
- Mid Price: ${kill_shot['mid_price']}
- Volume: {kill_shot['volume']:,}
- Open Interest: {kill_shot['open_interest']:,}
- Vol/OI Ratio: {round(kill_shot['volume'] / kill_shot['open_interest'], 2)}x
- Implied Volatility: {kill_shot['implied_volatility']}%
- Moneyness: {kill_shot['moneyness']} (1.0 = ATM)
- Bid-Ask Spread: {kill_shot['spread_pct']}%
- Composite Score: {kill_shot['composite_score']}/110

SCORING BREAKDOWN:
- Delta Score: {kill_shot['delta_score']}/100 (proximity to ATM)
- Vol/OI Score: {kill_shot['vol_oi_score']}/100 (unusual activity)
- Gamma Score: {kill_shot['gamma_score']}/100 (explosive potential)

Write a signal alert with these EXACT sections:
1. SIGNAL (one sentence, what and why)
2. SETUP (2-3 sentences on the technical setup)
3. KEY METRICS (3 bullet points on the most important data points)
4. RISK (one sentence on what invalidates this trade)

Keep total length under 150 words. Use plain English, no jargon overload.
Do NOT include price targets or specific entry/exit recommendations."""

    logger.info("Generating Kill Shot explanation via Groq...")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a professional options trading analyst. Be concise, data-driven, and clear."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=300
    )

    explanation = response.choices[0].message.content
    logger.info("Kill Shot explanation generated successfully.")

    output = {
        "ticker": kill_shot["ticker"],
        "strike": kill_shot["strike"],
        "expiry": kill_shot["expiry"],
        "option_type": kill_shot["option_type"],
        "composite_score": kill_shot["composite_score"],
        "explanation": explanation
    }

    with open("data/signal_output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Signal output saved to data/signal_output.json")
    return explanation