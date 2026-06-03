import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# Database
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "options_scanner"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres")
}

# Mode
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

# Schedule
SCAN_TIME = os.getenv("SCAN_TIME", "09:25")
MIDDAY_TIME = os.getenv("MIDDAY_TIME", "12:00")
EOD_TIME = os.getenv("EOD_TIME", "15:45")

# Scoring Weights
WEIGHTS = {
    "delta": float(os.getenv("WEIGHT_DELTA", 0.40)),
    "vol_oi": float(os.getenv("WEIGHT_VOL_OI", 0.35)),
    "gamma": float(os.getenv("WEIGHT_GAMMA", 0.25))
}

# Filters
FILTERS = {
    "min_open_interest": int(os.getenv("MIN_OPEN_INTEREST", 100)),
    "min_volume": int(os.getenv("MIN_VOLUME", 50)),
    "min_delta": float(os.getenv("MIN_DELTA", 0.20)),
    "max_delta": float(os.getenv("MAX_DELTA", 0.70))
}

# Ticker Universe — top liquid US equities + ETFs
# Ini 50 ticker paling likuid sebagai starting universe
# Lebih sedikit dari 4,000 tapi cukup untuk prove concept
# dan yfinance tidak akan timeout
TICKER_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "HYG",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "AVGO", "JPM", "V", "MA", "UNH", "JNJ", "XOM", "CVX",
    "BAC", "WMT", "HD", "PG", "KO", "PEP", "MRK", "ABBV",
    "LLY", "TMO", "COST", "ORCL", "CRM", "AMD", "INTC", "QCOM",
    "MU", "NFLX", "PYPL", "SQ", "ROKU", "SNAP", "UBER", "LYFT",
    "PLTR", "SOFI", "RIVN"
]