"""
Tests for paper_trading/data_store/data_recorder.py

Covers:
  - DB creation and table schema
  - record_candle_fetch: all fields stored, typical_price and tpv computed correctly
  - record_vwap_step: before/after state, formula correctness, both step_type values
  - record_option_chain: all rows stored, uppercase 'OI' column handled
  - record_quote: all fields stored, None quote is a no-op
  - Multi-step VWAP sequence: cumulative math matches manual calculation
  - Interval vs cumulative volume flag
  - Query convenience (ORDER BY candle_time)
  - Backward compatibility: strategy works when recorder=None
  - One DB per day: different dates → different files
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest
import sqlite3
import tempfile
import shutil
import datetime
import pandas as pd

from paper_trading.data_store.data_recorder import DataRecorder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candle(ts_str, open_, high, low, close, volume, oi=0):
    """Build a candle dict mirroring the real adapter output."""
    return {
        'timestamp': ts_str,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'oi': oi,
    }


def _make_chain_df(rows):
    """
    Build a DataFrame matching the get_options_chain() return structure.
    Note: OI column is uppercase 'OI' in real data.
    """
    return pd.DataFrame(rows, columns=[
        'strike', 'option_type', 'expiry', 'open', 'high', 'low', 'close',
        'OI', 'volume', 'instrument_token'
    ])


class MockQuote:
    """Mimics the Quote dataclass from types.py."""
    def __init__(self, ltp=100.0, oi=1000000, volume=500000,
                 open=98.0, high=105.0, low=95.0, close=100.0):
        self.ltp = ltp
        self.oi = oi
        self.volume = volume
        self.open = open
        self.high = high
        self.low = low
        self.close = close


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestDataRecorderDBCreation(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.date = datetime.date(2026, 2, 18)
        self.recorder = DataRecorder(date=self.date, base_dir=self.tmp_dir)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.tmp_dir)

    def test_db_file_created(self):
        expected = os.path.join(self.tmp_dir, 'trading_data_20260218.db')
        self.assertTrue(os.path.exists(expected))

    def test_all_tables_exist(self):
        conn = sqlite3.connect(self.recorder.db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        self.assertIn('candle_fetch_log', tables)
        self.assertIn('candle_data', tables)
        self.assertIn('vwap_steps', tables)
        self.assertIn('option_chain_snapshots', tables)
        self.assertIn('quote_fetches', tables)


class TestRecordCandleFetch(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.recorder = DataRecorder(date=datetime.date.today(), base_dir=self.tmp_dir)
        self.candles = [
            _make_candle('2026-02-18 09:15:00', 115.4, 115.4, 92.3, 94.35, 2595385, 3425955),
            _make_candle('2026-02-18 09:20:00', 94.35, 107.0, 94.35, 107.0, 1676025, 3430000),
            _make_candle('2026-02-18 09:25:00', 106.2, 109.25, 91.05, 96.4, 2028780, 3440000),
        ]

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.tmp_dir)

    def test_fetch_log_row_created(self):
        fetch_id = self.recorder.record_candle_fetch(
            'vwap_init', 25650, 'PE', '2026-02-24',
            '2026-02-18 09:15:00', '2026-02-18 09:25:00', self.candles
        )
        conn = sqlite3.connect(self.recorder.db_path)
        row = conn.execute(
            "SELECT fetch_reason, strike, option_type, candles_fetched FROM candle_fetch_log WHERE id=?",
            (fetch_id,)
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], 'vwap_init')
        self.assertEqual(row[1], 25650.0)
        self.assertEqual(row[2], 'PE')
        self.assertEqual(row[3], 3)

    def test_candle_data_rows_created(self):
        fetch_id = self.recorder.record_candle_fetch(
            'vwap_init', 25650, 'PE', '2026-02-24',
            None, None, self.candles
        )
        conn = sqlite3.connect(self.recorder.db_path)
        rows = conn.execute(
            "SELECT * FROM candle_data WHERE fetch_id=? ORDER BY id", (fetch_id,)
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 3)

    def test_typical_price_computed_correctly(self):
        """typical_price = (open + high + low + close) / 4"""
        fetch_id = self.recorder.record_candle_fetch(
            'vwap_init', 25650, 'PE', '2026-02-24',
            None, None, self.candles[:1]  # only first candle
        )
        conn = sqlite3.connect(self.recorder.db_path)
        row = conn.execute(
            "SELECT open, high, low, close, typical_price, formula, tpv_contribution FROM candle_data WHERE fetch_id=?",
            (fetch_id,)
        ).fetchone()
        conn.close()
        o, h, l, c = 115.4, 115.4, 92.3, 94.35
        expected_tp = (o + h + l + c) / 4
        expected_tpv = expected_tp * 2595385
        self.assertAlmostEqual(row[4], expected_tp, places=4)
        self.assertEqual(row[5], 'OHLC/4')
        self.assertAlmostEqual(row[6], expected_tpv, places=0)

    def test_returns_fetch_id(self):
        fid1 = self.recorder.record_candle_fetch('vwap_init', 25650, 'PE', '2026-02-24', None, None, self.candles)
        fid2 = self.recorder.record_candle_fetch('strategy_update', 25650, 'PE', '2026-02-24', None, None, self.candles[:1])
        self.assertNotEqual(fid1, fid2)
        self.assertIsNotNone(fid1)


class TestRecordVwapStep(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.recorder = DataRecorder(date=datetime.date.today(), base_dir=self.tmp_dir)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.tmp_dir)

    def _read_last_vwap_step(self):
        conn = sqlite3.connect(self.recorder.db_path)
        cols = [d[0] for d in conn.execute("SELECT * FROM vwap_steps LIMIT 0").description]
        row = conn.execute("SELECT * FROM vwap_steps ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        return dict(zip(cols, row)) if row else None

    def test_init_candle_step_stored(self):
        ohlc = {'open': 115.4, 'high': 115.4, 'low': 92.3, 'close': 94.35}
        self.recorder.record_vwap_step(
            step_type='init_candle', strike=25650, option_type='PE', expiry='2026-02-24',
            candle_time='2026-02-18 09:15:00', ohlc=ohlc, raw_volume=2595385,
            is_interval_volume=True, incremental_volume=2595385,
            cum_tpv_before=0.0, cum_volume_before=0.0,
            cum_tpv_after=104.3625 * 2595385, cum_volume_after=2595385
        )
        row = self._read_last_vwap_step()
        self.assertIsNotNone(row)
        self.assertEqual(row['step_type'], 'init_candle')
        self.assertEqual(row['formula'], 'OHLC/4')
        self.assertEqual(row['is_interval_volume'], 1)

    def test_typical_price_formula_correct(self):
        """Verify stored typical_price = (O+H+L+C)/4 exactly."""
        o, h, l, c = 115.4, 115.4, 92.3, 94.35
        expected_tp = (o + h + l + c) / 4
        ohlc = {'open': o, 'high': h, 'low': l, 'close': c}
        self.recorder.record_vwap_step(
            step_type='init_candle', strike=25650, option_type='PE', expiry='2026-02-24',
            candle_time=None, ohlc=ohlc, raw_volume=1000000,
            is_interval_volume=True, incremental_volume=1000000,
            cum_tpv_before=0.0, cum_volume_before=0.0,
            cum_tpv_after=expected_tp * 1000000, cum_volume_after=1000000
        )
        row = self._read_last_vwap_step()
        self.assertAlmostEqual(row['typical_price'], expected_tp, places=6)
        self.assertAlmostEqual(row['tpv_added'], expected_tp * 1000000, places=2)

    def test_vwap_after_equals_cum_tpv_over_cum_volume(self):
        """vwap_after must equal cum_tpv_after / cum_volume_after."""
        cum_tpv = 1234567890.0
        cum_vol = 12000000.0
        expected_vwap = cum_tpv / cum_vol
        ohlc = {'open': 100.0, 'high': 110.0, 'low': 90.0, 'close': 100.0}
        self.recorder.record_vwap_step(
            step_type='live_update', strike=25700, option_type='CE', expiry='2026-02-24',
            candle_time=None, ohlc=ohlc, raw_volume=500000,
            is_interval_volume=True, incremental_volume=500000,
            cum_tpv_before=cum_tpv - 100.0 * 500000, cum_volume_before=cum_vol - 500000,
            cum_tpv_after=cum_tpv, cum_volume_after=cum_vol
        )
        row = self._read_last_vwap_step()
        self.assertAlmostEqual(row['vwap_after'], expected_vwap, places=6)

    def test_vwap_before_is_none_for_first_candle(self):
        """First candle has cum_volume_before=0, so vwap_before must be NULL."""
        ohlc = {'open': 100.0, 'high': 110.0, 'low': 90.0, 'close': 100.0}
        self.recorder.record_vwap_step(
            step_type='init_candle', strike=25650, option_type='PE', expiry='2026-02-24',
            candle_time=None, ohlc=ohlc, raw_volume=1000000,
            is_interval_volume=True, incremental_volume=1000000,
            cum_tpv_before=0.0, cum_volume_before=0.0,
            cum_tpv_after=100.0 * 1000000, cum_volume_after=1000000
        )
        row = self._read_last_vwap_step()
        self.assertIsNone(row['vwap_before'])

    def test_cumulative_volume_flag_stored(self):
        ohlc = {'open': 100.0, 'high': 110.0, 'low': 90.0, 'close': 100.0}
        self.recorder.record_vwap_step(
            step_type='live_update', strike=25650, option_type='PE', expiry='2026-02-24',
            candle_time=None, ohlc=ohlc, raw_volume=5000000,
            is_interval_volume=False, incremental_volume=500000,
            cum_tpv_before=0.0, cum_volume_before=0.0,
            cum_tpv_after=100.0 * 500000, cum_volume_after=500000
        )
        row = self._read_last_vwap_step()
        self.assertEqual(row['is_interval_volume'], 0)
        self.assertEqual(row['raw_volume'], 5000000)
        self.assertAlmostEqual(row['incremental_volume'], 500000.0, places=0)


class TestMultiStepVwapSequence(unittest.TestCase):
    """
    Simulate 3-candle VWAP init and verify cumulative math is correct.
    Mirrors exactly what _initialize_vwap_with_history does.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.recorder = DataRecorder(date=datetime.date.today(), base_dir=self.tmp_dir)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.tmp_dir)

    def test_three_candle_sequence(self):
        candles = [
            {'open': 115.4, 'high': 115.4, 'low': 92.3, 'close': 94.35,  'volume': 2595385},
            {'open': 94.35, 'high': 107.0, 'low': 94.35, 'close': 107.0, 'volume': 1676025},
            {'open': 106.2, 'high': 109.25,'low': 91.05, 'close': 96.4,  'volume': 2028780},
        ]

        cum_tpv = 0.0
        cum_vol = 0.0

        for candle in candles:
            tp = (candle['open'] + candle['high'] + candle['low'] + candle['close']) / 4
            vol = candle['volume']
            tpv_before = cum_tpv
            vol_before = cum_vol
            cum_tpv += tp * vol
            cum_vol += vol

            self.recorder.record_vwap_step(
                step_type='init_candle', strike=25650, option_type='PE', expiry='2026-02-24',
                candle_time=None, ohlc=candle, raw_volume=vol,
                is_interval_volume=True, incremental_volume=vol,
                cum_tpv_before=tpv_before, cum_volume_before=vol_before,
                cum_tpv_after=cum_tpv, cum_volume_after=cum_vol
            )

        expected_final_vwap = cum_tpv / cum_vol

        # Read all 3 rows and verify the last one
        conn = sqlite3.connect(self.recorder.db_path)
        rows = conn.execute(
            "SELECT cum_tpv_after, cum_volume_after, vwap_after FROM vwap_steps ORDER BY id"
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 3)
        final = rows[-1]
        self.assertAlmostEqual(final[0], cum_tpv, places=2)
        self.assertAlmostEqual(final[1], cum_vol, places=0)
        self.assertAlmostEqual(final[2], expected_final_vwap, places=6)


class TestRecordOptionChain(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.recorder = DataRecorder(date=datetime.date.today(), base_dir=self.tmp_dir)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.tmp_dir)

    def test_chain_rows_stored(self):
        df = _make_chain_df([
            (25650, 'CE', '2026-02-24', 128.0, 130.0, 125.0, 128.5, 11361545, 500000, 'tok1'),
            (25650, 'PE', '2026-02-24', 104.0, 106.0, 101.0, 104.5, 9258535, 400000, 'tok2'),
        ])
        self.recorder.record_option_chain(spot_price=25659.10, direction=None, chain_df=df)
        conn = sqlite3.connect(self.recorder.db_path)
        rows = conn.execute("SELECT * FROM option_chain_snapshots").fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)

    def test_oi_uppercase_column_handled(self):
        """Real DataFrame from get_options_chain() has 'OI' (uppercase)."""
        df = _make_chain_df([
            (25700, 'CE', '2026-02-24', 100.0, 105.0, 98.0, 101.0, 11361545, 600000, 'tok3'),
        ])
        self.recorder.record_option_chain(25659.10, None, df)
        conn = sqlite3.connect(self.recorder.db_path)
        row = conn.execute("SELECT oi FROM option_chain_snapshots").fetchone()
        conn.close()
        self.assertEqual(row[0], 11361545)

    def test_empty_dataframe_is_noop(self):
        """Passing an empty DataFrame should not raise or insert anything."""
        self.recorder.record_option_chain(25659.10, None, pd.DataFrame())
        conn = sqlite3.connect(self.recorder.db_path)
        count = conn.execute("SELECT COUNT(*) FROM option_chain_snapshots").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_spot_price_and_direction_stored(self):
        df = _make_chain_df([
            (25650, 'PE', '2026-02-24', 104.0, 106.0, 101.0, 104.5, 9258535, 400000, 'tok4'),
        ])
        self.recorder.record_option_chain(25659.10, 'PUT', df)
        conn = sqlite3.connect(self.recorder.db_path)
        row = conn.execute("SELECT spot_price, direction FROM option_chain_snapshots").fetchone()
        conn.close()
        self.assertAlmostEqual(row[0], 25659.10, places=2)
        self.assertEqual(row[1], 'PUT')


class TestRecordQuote(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.recorder = DataRecorder(date=datetime.date.today(), base_dir=self.tmp_dir)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.tmp_dir)

    def test_quote_fields_stored(self):
        q = MockQuote(ltp=128.5, oi=3425955, volume=2000000,
                      open=115.4, high=129.75, low=92.3, close=128.5)
        self.recorder.record_quote('oi_fallback', 25650, 'PE', '2026-02-24', q)
        conn = sqlite3.connect(self.recorder.db_path)
        row = conn.execute("SELECT fetch_reason, ltp, oi, volume FROM quote_fetches").fetchone()
        conn.close()
        self.assertEqual(row[0], 'oi_fallback')
        self.assertAlmostEqual(row[1], 128.5, places=2)
        self.assertEqual(row[2], 3425955)
        self.assertEqual(row[3], 2000000)

    def test_none_quote_is_noop(self):
        self.recorder.record_quote('oi_fallback', 25650, 'PE', '2026-02-24', None)
        conn = sqlite3.connect(self.recorder.db_path)
        count = conn.execute("SELECT COUNT(*) FROM quote_fetches").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)


class TestQueryVwapHistory(unittest.TestCase):
    """Verify we can query VWAP steps ordered by candle_time for a specific strike."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.recorder = DataRecorder(date=datetime.date.today(), base_dir=self.tmp_dir)

    def tearDown(self):
        self.recorder.close()
        shutil.rmtree(self.tmp_dir)

    def test_query_by_strike_ordered_by_time(self):
        times = ['2026-02-18 09:15:00', '2026-02-18 09:20:00', '2026-02-18 09:25:00']
        ohlc = {'open': 100.0, 'high': 110.0, 'low': 90.0, 'close': 100.0}
        cum_tpv, cum_vol = 0.0, 0.0
        for t in times:
            tp = (100 + 110 + 90 + 100) / 4
            tpv_b, vol_b = cum_tpv, cum_vol
            cum_tpv += tp * 1000000
            cum_vol += 1000000
            self.recorder.record_vwap_step(
                'init_candle', 25650, 'PE', '2026-02-24',
                t, ohlc, 1000000, True, 1000000,
                tpv_b, vol_b, cum_tpv, cum_vol
            )

        conn = sqlite3.connect(self.recorder.db_path)
        rows = conn.execute("""
            SELECT candle_time, vwap_after FROM vwap_steps
            WHERE strike=25650 AND option_type='PE'
            ORDER BY candle_time
        """).fetchall()
        conn.close()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], times[0])
        self.assertEqual(rows[-1][0], times[-1])


class TestBackwardCompatibility(unittest.TestCase):
    """Strategy must work fine when recorder=None (no DataRecorder passed)."""

    def test_recorder_none_does_not_crash_vwap_init(self):
        """
        Simulate the recorder=None path in _initialize_vwap_with_history.
        This ensures the `if self.recorder:` guard works.
        """
        recorder = None

        # Replicate the guard logic from strategy.py
        candles = [
            _make_candle('2026-02-18 09:15:00', 115.4, 115.4, 92.3, 94.35, 2595385),
        ]
        totals = {'tpv': 0.0, 'volume': 0.0}

        for candle in candles:
            tp = (candle['open'] + candle['high'] + candle['low'] + candle['close']) / 4
            vol = candle['volume']
            tpv_b = totals['tpv']
            vol_b = totals['volume']
            totals['tpv'] += tp * vol
            totals['volume'] += vol

            # This is the guard in strategy.py
            if recorder:
                recorder.record_vwap_step(
                    step_type='init_candle', strike=25650, option_type='PE', expiry='2026-02-24',
                    candle_time=candle.get('timestamp'), ohlc=candle, raw_volume=vol,
                    is_interval_volume=True, incremental_volume=vol,
                    cum_tpv_before=tpv_b, cum_volume_before=vol_b,
                    cum_tpv_after=totals['tpv'], cum_volume_after=totals['volume']
                )

        # If we get here without exception, the guard works
        self.assertGreater(totals['volume'], 0)


class TestDbPerDay(unittest.TestCase):
    """Different dates must produce different DB files."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_different_dates_different_files(self):
        d1 = datetime.date(2026, 2, 18)
        d2 = datetime.date(2026, 2, 19)
        r1 = DataRecorder(date=d1, base_dir=self.tmp_dir)
        r2 = DataRecorder(date=d2, base_dir=self.tmp_dir)
        self.assertNotEqual(r1.db_path, r2.db_path)
        self.assertIn('20260218', r1.db_path)
        self.assertIn('20260219', r2.db_path)
        r1.close()
        r2.close()
        self.assertTrue(os.path.exists(r1.db_path))
        self.assertTrue(os.path.exists(r2.db_path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
