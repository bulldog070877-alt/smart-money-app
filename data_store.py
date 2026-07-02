"""
Persistent cache for yfinance OHLCV history, backed by Neon Postgres.

Historical bars are stored once and never re-downloaded. On each call we
only ask yfinance for bars newer than what's already in the database
("incremental top-up"), which keeps requests small and lets the app keep
working off the cached data if yfinance is rate-limited or unreachable.

Using Postgres (instead of a local SQLite file) means the cache survives
redeploys/restarts on Streamlit Community Cloud, where local disk is wiped
on every new container.

Requires a NEON_DATABASE_URL connection string in Streamlit secrets
(.streamlit/secrets.toml locally, or the app's "Secrets" settings on
Streamlit Cloud) or the NEON_DATABASE_URL environment variable.
"""
import os

import pandas as pd
import psycopg2
import streamlit as st
import yfinance as yf

_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

# How far back to backfill a symbol the first time it's cached. Kept small to
# manage Neon storage/free-tier limits - bump this (or pass years= explicitly
# to get_history) once storage headroom allows more history.
DEFAULT_HISTORY_YEARS = 3

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    PRIMARY KEY (symbol, interval, date)
)
"""


def connection_string():
    if "NEON_DATABASE_URL" in st.secrets:
        return st.secrets["NEON_DATABASE_URL"]
    return os.environ["NEON_DATABASE_URL"]


def _get_conn():
    conn = psycopg2.connect(connection_string(), connect_timeout=10)
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def _read_cached(conn, symbol, interval):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT date, open, high, low, close, volume FROM prices "
            "WHERE symbol=%s AND interval=%s ORDER BY date",
            (symbol, interval),
        )
        rows = cur.fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date"] + _COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.index.name = None
    return df


def _write_cache(conn, symbol, interval, df):
    if df is None or len(df) == 0:
        return
    rows = [
        (symbol, interval, idx.to_pydatetime(),
         float(r.Open), float(r.High), float(r.Low), float(r.Close), float(r.Volume))
        for idx, r in df.iterrows()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO prices (symbol, interval, date, open, high, low, close, volume)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (symbol, interval, date) DO UPDATE SET
                open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                close = EXCLUDED.close, volume = EXCLUDED.volume
            """,
            rows,
        )
    conn.commit()


def _fetch_from_yfinance(symbol, interval, start):
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, interval=interval, timeout=15)
    if df is None or len(df) == 0:
        return None
    df.index = df.index.tz_localize(None)
    return df[_COLUMNS]


@st.cache_data(ttl=3600, show_spinner=False)
def get_history(symbol, interval, years=DEFAULT_HISTORY_YEARS):
    """Return OHLCV history for symbol/interval, serving from the Neon
    cache and only pulling new bars from yfinance. Falls back to whatever
    is cached if yfinance fails (rate limit, network, etc.).

    The first time a symbol/interval is cached, only the last `years` of
    history is backfilled (not the full available history) to keep storage
    small. Every call after that just tops up new bars, regardless of
    `years` - it's only consulted for the initial backfill."""
    conn = _get_conn()
    try:
        cached = _read_cached(conn, symbol, interval)
        if cached is None:
            start = pd.Timestamp.now() - pd.DateOffset(years=years)
            fresh = _fetch_from_yfinance(symbol, interval, start=start)
            if fresh is None:
                return None
            _write_cache(conn, symbol, interval, fresh)
            return fresh

        try:
            incremental = _fetch_from_yfinance(symbol, interval, start=cached.index.max())
            if incremental is not None and len(incremental) > 0:
                _write_cache(conn, symbol, interval, incremental)
                cached = _read_cached(conn, symbol, interval)
        except Exception:
            pass  # yfinance unavailable/rate-limited - serve what's cached

        return cached
    finally:
        conn.close()
