"""
DataRecorder — Persistent SQLite store for all fetched market data and VWAP calculations.

One DB file per trading day: paper_trading/data_store/trading_data_YYYYMMDD.db

Tables
------
candle_fetch_log      — one row per get_historical_candles() API call
candle_data           — one row per individual candle in any fetch (OHLC + computed fields)
vwap_steps            — every single VWAP update step, init or live, with full before/after state
option_chain_snapshots — full option chain at direction-determination time
quote_fetches          — individual quote API calls (OI fallback, LTP monitoring)

VWAP formula stored: OHLC/4  →  typical_price = (open + high + low + close) / 4
                     tpv_added = typical_price × incremental_volume
                     vwap_after = cum_tpv_after / cum_volume_after
"""

import sqlite3
import datetime
import os
from pathlib import Path


class DataRecorder:
    """
    Records all market data fetches and VWAP calculations to a SQLite database.

    Usage:
        recorder = DataRecorder(date=datetime.date.today(), base_dir='paper_trading/data_store')
        fetch_id = recorder.record_candle_fetch(...)
        recorder.record_vwap_step(...)
        recorder.record_option_chain(...)
        recorder.record_quote(...)
        recorder.close()
    """

    FORMULA = 'OHLC/4'  # (open + high + low + close) / 4

    def __init__(self, date: datetime.date, base_dir: str):
        """
        Args:
            date:     Trading date (used to name the DB file).
            base_dir: Directory where DB files are stored.
        """
        os.makedirs(base_dir, exist_ok=True)
        db_name = f"trading_data_{date.strftime('%Y%m%d')}.db"
        self.db_path = os.path.join(base_dir, db_name)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")   # allow concurrent reads
        self._conn.execute("PRAGMA synchronous=NORMAL") # fast enough, still safe
        self._init_tables()
        print(f"[DataRecorder] DB: {self.db_path}")

    # ------------------------------------------------------------------
    # Table creation
    # ------------------------------------------------------------------

    def _init_tables(self):
        c = self._conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS candle_fetch_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at      TEXT NOT NULL,
                fetch_reason    TEXT NOT NULL,   -- vwap_init | strategy_update
                strike          REAL NOT NULL,
                option_type     TEXT NOT NULL,   -- CE | PE
                expiry          TEXT NOT NULL,
                from_time       TEXT,
                to_time         TEXT,
                candles_fetched INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS candle_data (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fetch_id        INTEGER NOT NULL, -- FK → candle_fetch_log.id
                fetched_at      TEXT NOT NULL,
                strike          REAL NOT NULL,
                option_type     TEXT NOT NULL,
                expiry          TEXT NOT NULL,
                candle_time     TEXT,
                open            REAL,
                high            REAL,
                low             REAL,
                close           REAL,
                volume          INTEGER,
                oi              INTEGER,
                -- Computed fields stored for reference
                typical_price   REAL,            -- (open+high+low+close)/4
                formula         TEXT,            -- 'OHLC/4'
                tpv_contribution REAL            -- typical_price * volume
            );

            CREATE TABLE IF NOT EXISTS vwap_steps (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at         TEXT NOT NULL,
                step_type           TEXT NOT NULL,  -- init_candle | live_update
                strike              REAL NOT NULL,
                option_type         TEXT NOT NULL,
                expiry              TEXT NOT NULL,
                candle_time         TEXT,
                -- Raw candle
                open                REAL,
                high                REAL,
                low                 REAL,
                close               REAL,
                raw_volume          INTEGER,
                -- Volume handling
                is_interval_volume  INTEGER,        -- 1=interval(per-candle) 0=cumulative
                incremental_volume  REAL,           -- volume actually used (may differ from raw)
                -- Step calculation
                typical_price       REAL,           -- (O+H+L+C)/4
                formula             TEXT,           -- 'OHLC/4'
                tpv_added           REAL,           -- typical_price * incremental_volume
                -- State BEFORE this candle
                cum_tpv_before      REAL,
                cum_volume_before   REAL,
                vwap_before         REAL,           -- NULL if first candle
                -- State AFTER this candle
                cum_tpv_after       REAL,
                cum_volume_after    REAL,
                vwap_after          REAL            -- cum_tpv_after / cum_volume_after
            );

            CREATE TABLE IF NOT EXISTS option_chain_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at      TEXT NOT NULL,
                spot_price      REAL,
                direction       TEXT,            -- CALL | PUT | NULL (before determination)
                strike          REAL NOT NULL,
                option_type     TEXT NOT NULL,   -- CE | PE
                expiry          TEXT,
                ltp             REAL,
                oi              INTEGER,
                volume          INTEGER,
                instrument_token TEXT
            );

            CREATE TABLE IF NOT EXISTS quote_fetches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at      TEXT NOT NULL,
                fetch_reason    TEXT NOT NULL,   -- oi_fallback | ltp_monitoring | exit_check
                strike          REAL NOT NULL,
                option_type     TEXT NOT NULL,
                expiry          TEXT NOT NULL,
                ltp             REAL,
                oi              INTEGER,
                volume          INTEGER,
                open            REAL,
                high            REAL,
                low             REAL,
                close           REAL
            );
        """)
        c.commit()

    # ------------------------------------------------------------------
    # Public recording methods
    # ------------------------------------------------------------------

    def record_candle_fetch(self, fetch_reason: str, strike, option_type: str,
                            expiry, from_time, to_time, candles: list) -> int:
        """
        Record one get_historical_candles() API call and all candles it returned.

        Args:
            fetch_reason:  'vwap_init' or 'strategy_update'
            strike:        Strike price (int or float)
            option_type:   'CE' or 'PE'
            expiry:        Expiry date (any str-able value)
            from_time:     Start of fetch window (datetime or str)
            to_time:       End of fetch window (datetime or str)
            candles:       List of candle dicts: {timestamp, open, high, low, close, volume, oi}

        Returns:
            fetch_id:  Row ID in candle_fetch_log (use to correlate candle_data rows)
        """
        now = _ts()
        expiry_str = str(expiry)
        from_str = str(from_time) if from_time else None
        to_str = str(to_time) if to_time else None

        cur = self._conn.execute(
            """INSERT INTO candle_fetch_log
               (fetched_at, fetch_reason, strike, option_type, expiry,
                from_time, to_time, candles_fetched)
               VALUES (?,?,?,?,?,?,?,?)""",
            (now, fetch_reason, float(strike), option_type, expiry_str,
             from_str, to_str, len(candles))
        )
        fetch_id = cur.lastrowid

        rows = []
        for candle in candles:
            o = candle.get('open', 0) or 0
            h = candle.get('high', 0) or 0
            l = candle.get('low', 0) or 0
            c = candle.get('close', 0) or 0
            vol = candle.get('volume', 0) or 0
            oi = candle.get('oi', 0) or 0
            tp = (o + h + l + c) / 4
            tpv = tp * vol
            candle_time = str(candle.get('timestamp', '')) if candle.get('timestamp') else None
            rows.append((
                fetch_id, now, float(strike), option_type, expiry_str,
                candle_time, o, h, l, c, int(vol), int(oi),
                tp, self.FORMULA, tpv
            ))

        self._conn.executemany(
            """INSERT INTO candle_data
               (fetch_id, fetched_at, strike, option_type, expiry,
                candle_time, open, high, low, close, volume, oi,
                typical_price, formula, tpv_contribution)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows
        )
        self._conn.commit()
        return fetch_id

    def record_vwap_step(self, step_type: str, strike, option_type: str, expiry,
                         candle_time, ohlc: dict, raw_volume: int,
                         is_interval_volume: bool, incremental_volume: float,
                         cum_tpv_before: float, cum_volume_before: float,
                         cum_tpv_after: float, cum_volume_after: float):
        """
        Record one VWAP calculation step with full before/after state.

        Formula stored:
            typical_price  = (open + high + low + close) / 4        [OHLC/4]
            tpv_added      = typical_price × incremental_volume
            vwap_after     = cum_tpv_after / cum_volume_after

        Args:
            step_type:           'init_candle' (during VWAP init) or 'live_update' (new candle)
            strike:              Strike price
            option_type:         'CE' or 'PE'
            expiry:              Expiry date
            candle_time:         Candle timestamp (datetime or str)
            ohlc:                Dict with keys: open, high, low, close
            raw_volume:          Volume as reported by broker
            is_interval_volume:  True if broker returns per-candle volume; False if cumulative
            incremental_volume:  Actual volume used for this step (may == raw if interval)
            cum_tpv_before:      Cumulative TPV before adding this candle
            cum_volume_before:   Cumulative volume before adding this candle
            cum_tpv_after:       Cumulative TPV after adding this candle
            cum_volume_after:    Cumulative volume after adding this candle
        """
        o = ohlc.get('open', 0) or 0
        h = ohlc.get('high', 0) or 0
        l = ohlc.get('low', 0) or 0
        c = ohlc.get('close', 0) or 0
        tp = (o + h + l + c) / 4
        tpv_added = tp * incremental_volume

        vwap_before = (cum_tpv_before / cum_volume_before) if cum_volume_before > 0 else None
        vwap_after = (cum_tpv_after / cum_volume_after) if cum_volume_after > 0 else tp

        self._conn.execute(
            """INSERT INTO vwap_steps
               (recorded_at, step_type, strike, option_type, expiry, candle_time,
                open, high, low, close, raw_volume,
                is_interval_volume, incremental_volume,
                typical_price, formula, tpv_added,
                cum_tpv_before, cum_volume_before, vwap_before,
                cum_tpv_after,  cum_volume_after,  vwap_after)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_ts(), step_type, float(strike), option_type, str(expiry),
             str(candle_time) if candle_time else None,
             o, h, l, c, int(raw_volume),
             1 if is_interval_volume else 0, float(incremental_volume),
             tp, self.FORMULA, tpv_added,
             cum_tpv_before, cum_volume_before, vwap_before,
             cum_tpv_after, cum_volume_after, vwap_after)
        )
        self._conn.commit()

    def record_option_chain(self, spot_price, direction, chain_df):
        """
        Record a full option chain snapshot (from get_options_chain() call).

        Args:
            spot_price:  Current Nifty spot price
            direction:   'CALL', 'PUT', or None (if not yet determined)
            chain_df:    pandas DataFrame with columns: strike, option_type, expiry,
                         open/high/low/close (LTP), OI (uppercase), volume, instrument_token
        """
        if chain_df is None or chain_df.empty:
            return

        now = _ts()
        rows = []
        for _, row in chain_df.iterrows():
            # OI column is uppercase 'OI' in the DataFrame from get_options_chain()
            oi_val = row.get('OI', row.get('oi', 0))
            rows.append((
                now,
                float(spot_price) if spot_price else None,
                direction,
                float(row.get('strike', 0)),
                str(row.get('option_type', '')),
                str(row.get('expiry', '')),
                float(row.get('close', row.get('ltp', 0)) or 0),  # LTP stored in close col
                int(oi_val or 0),
                int(row.get('volume', 0) or 0),
                str(row.get('instrument_token', ''))
            ))

        self._conn.executemany(
            """INSERT INTO option_chain_snapshots
               (fetched_at, spot_price, direction, strike, option_type, expiry,
                ltp, oi, volume, instrument_token)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            rows
        )
        self._conn.commit()

    def record_quote(self, fetch_reason: str, strike, option_type: str, expiry, quote):
        """
        Record a single quote API fetch (OI fallback, LTP monitoring, etc.).

        Args:
            fetch_reason:  'oi_fallback', 'ltp_monitoring', 'exit_check', etc.
            strike:        Strike price
            option_type:   'CE' or 'PE'
            expiry:        Expiry date
            quote:         Quote object/dataclass with fields: ltp, oi, volume,
                           open, high, low, close (or None if fetch failed)
        """
        if quote is None:
            return

        self._conn.execute(
            """INSERT INTO quote_fetches
               (fetched_at, fetch_reason, strike, option_type, expiry,
                ltp, oi, volume, open, high, low, close)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_ts(), fetch_reason, float(strike), option_type, str(expiry),
             getattr(quote, 'ltp', None),
             getattr(quote, 'oi', None),
             getattr(quote, 'volume', None),
             getattr(quote, 'open', None),
             getattr(quote, 'high', None),
             getattr(quote, 'low', None),
             getattr(quote, 'close', None))
        )
        self._conn.commit()

    def close(self):
        """Flush and close the database connection."""
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None
            print(f"[DataRecorder] Closed: {self.db_path}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _ts() -> str:
    """Current timestamp as ISO string."""
    return datetime.datetime.now().isoformat(timespec='milliseconds')
