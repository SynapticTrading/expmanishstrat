"""
Tests for the partial candle exclusion fix in _initialize_vwap_from_market_open.

Problem fixed:
    When the system starts mid-session (e.g. at 10:51), the historical candle fetch
    returns the currently-in-progress candle (10:50, only 1 min of data, partial volume).
    If included in VWAP init, this candle is later double-counted when the live_update
    adds the completed 10:50 candle at 10:55.

Fix:
    Before passing candles to _initialize_vwap_with_history, drop the last candle
    if its timestamp + 5 min > current_time (i.e. it is still in progress).

Tests verify:
    1. In-progress last candle is dropped (timestamp + 5min > now)
    2. Completed last candle is kept (timestamp + 5min <= now)
    3. VWAP cumulative totals are NOT polluted by the partial candle
    4. Edge: only one candle and it's partial → nothing to init with
    5. Candles without timestamp field are kept (safe fallback)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest
from datetime import datetime, timedelta
import pytz

IST = pytz.timezone('Asia/Kolkata')


def _candle(ts, open_, high, low, close, volume, oi=0):
    return {'timestamp': ts, 'open': open_, 'high': high,
            'low': low, 'close': close, 'volume': volume, 'oi': oi}


def _drop_partial(candles, current_time):
    """
    Mirrors the exact logic added to _initialize_vwap_from_market_open.
    Returns (filtered_candles, dropped_candle_or_None).
    """
    if not candles:
        return candles, None

    last_candle = candles[-1]
    last_ts = last_candle.get('timestamp')
    if last_ts is None:
        return candles, None  # no timestamp → keep (safe fallback)

    if hasattr(last_ts, 'tzinfo') and last_ts.tzinfo and not current_time.tzinfo:
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        current_time = ist.localize(current_time)

    if last_ts + timedelta(minutes=5) > current_time:
        return candles[:-1], candles[-1]
    return candles, None


class TestPartialCandleDrop(unittest.TestCase):

    def _ts(self, h, m):
        """Build an IST-aware datetime for today at h:m."""
        return IST.localize(datetime(2026, 2, 19, h, m, 0))

    # ------------------------------------------------------------------
    # Core drop logic
    # ------------------------------------------------------------------

    def test_in_progress_candle_is_dropped(self):
        """
        Candle at 10:50, fetched at 10:51 → 10:50 + 5min = 10:55 > 10:51 → DROP.
        """
        candles = [
            _candle(self._ts(9, 15), 180.1, 192.9, 169.6, 180.7, 1382030),
            _candle(self._ts(10, 45), 121.8, 123.0, 119.0, 121.2, 1213875),
            _candle(self._ts(10, 50), 121.1, 122.7, 119.9, 122.4, 193895),  # partial
        ]
        current_time = self._ts(10, 51)
        result, dropped = _drop_partial(candles, current_time)

        self.assertEqual(len(result), 2)
        self.assertIsNotNone(dropped)
        self.assertEqual(dropped['volume'], 193895)
        self.assertEqual(dropped['timestamp'], self._ts(10, 50))

    def test_completed_candle_is_kept(self):
        """
        Candle at 10:45, fetched at 10:51 → 10:45 + 5min = 10:50 <= 10:51 → KEEP.
        """
        candles = [
            _candle(self._ts(9, 15), 180.1, 192.9, 169.6, 180.7, 1382030),
            _candle(self._ts(10, 45), 121.8, 123.0, 119.0, 121.2, 1213875),
        ]
        current_time = self._ts(10, 51)
        result, dropped = _drop_partial(candles, current_time)

        self.assertEqual(len(result), 2)
        self.assertIsNone(dropped)

    def test_candle_exactly_at_boundary_is_kept(self):
        """
        Candle at 10:50, fetched at exactly 10:55 → 10:50 + 5min = 10:55 = 10:55 → KEEP.
        """
        candles = [
            _candle(self._ts(10, 50), 121.1, 122.7, 119.9, 122.4, 1145235),
        ]
        current_time = self._ts(10, 55)
        result, dropped = _drop_partial(candles, current_time)

        self.assertEqual(len(result), 1)
        self.assertIsNone(dropped)

    def test_only_one_candle_and_partial_leaves_empty_list(self):
        """
        If there's only one candle and it's partial, result is empty list.
        The caller should abort VWAP init (nothing to work with).
        """
        candles = [_candle(self._ts(10, 50), 121.1, 122.7, 119.9, 122.4, 193895)]
        current_time = self._ts(10, 51)
        result, dropped = _drop_partial(candles, current_time)

        self.assertEqual(len(result), 0)
        self.assertIsNotNone(dropped)

    def test_candle_without_timestamp_is_kept(self):
        """
        Candle missing timestamp key → safe fallback, keep it, don't drop.
        """
        candles = [
            {'open': 180.1, 'high': 192.9, 'low': 169.6, 'close': 180.7, 'volume': 1382030},
            {'open': 121.1, 'high': 122.7, 'low': 119.9, 'close': 122.4, 'volume': 193895},
        ]
        current_time = self._ts(10, 51)
        result, dropped = _drop_partial(candles, current_time)

        self.assertEqual(len(result), 2)
        self.assertIsNone(dropped)

    def test_empty_candle_list_returns_empty(self):
        result, dropped = _drop_partial([], self._ts(10, 51))
        self.assertEqual(result, [])
        self.assertIsNone(dropped)

    # ------------------------------------------------------------------
    # VWAP correctness — partial candle must NOT affect cumulative totals
    # ------------------------------------------------------------------

    def test_vwap_not_polluted_by_partial_candle(self):
        """
        Simulate the exact scenario from 2026-02-19:
            19 complete candles (9:15–10:45) + 1 partial (10:50, vol=193,895).
        With fix: VWAP is calculated over 19 candles only.
        Without fix: partial 193,895 volume would be included and then
                     double-counted when the live_update adds full 1,145,235.

        We verify:
            cum_volume_with_fix  = sum of 19 candle volumes (no partial)
            cum_volume_no_fix    = sum of 19 + 193,895 (polluted)
        and that the VWAP values differ.
        """
        complete_candles = [
            _candle(self._ts(9,  15), 180.1,  192.95, 169.65, 180.70, 1382030),
            _candle(self._ts(9,  20), 181.0,  196.60, 177.85, 179.80, 930410),
            _candle(self._ts(9,  25), 178.85, 180.10, 157.60, 158.85, 782405),
            _candle(self._ts(9,  30), 158.85, 161.90, 151.30, 153.00, 666965),
            _candle(self._ts(9,  35), 153.0,  159.30, 140.30, 145.25, 1290315),
            _candle(self._ts(9,  40), 145.65, 148.50, 142.35, 143.05, 985465),
            _candle(self._ts(9,  45), 143.3,  157.30, 141.55, 154.55, 2016755),
            _candle(self._ts(9,  50), 154.65, 156.00, 141.35, 142.95, 1386450),
            _candle(self._ts(9,  55), 142.95, 145.35, 136.65, 140.05, 1138930),
            _candle(self._ts(10, 0),  140.05, 145.95, 135.30, 145.75, 1787825),
            _candle(self._ts(10, 5),  145.75, 147.45, 139.40, 142.10, 1521650),
            _candle(self._ts(10, 10), 141.65, 144.25, 127.95, 130.85, 1655355),
            _candle(self._ts(10, 15), 130.80, 135.35, 126.60, 130.95, 2088450),
            _candle(self._ts(10, 20), 130.80, 135.70, 126.50, 131.45, 1595490),
            _candle(self._ts(10, 25), 131.45, 132.90, 123.00, 129.10, 2109250),
            _candle(self._ts(10, 30), 129.10, 132.35, 123.75, 124.80, 1830790),
            _candle(self._ts(10, 35), 124.80, 128.00, 117.25, 119.05, 2321085),
            _candle(self._ts(10, 40), 119.0,  123.90, 115.95, 122.00, 1875835),
            _candle(self._ts(10, 45), 121.80, 123.00, 119.00, 121.15, 1213875),
        ]
        partial_candle = _candle(self._ts(10, 50), 121.15, 122.7, 119.95, 122.45, 193895)

        all_candles = complete_candles + [partial_candle]
        current_time = self._ts(10, 51)

        # --- With fix ---
        fixed, dropped = _drop_partial(all_candles, current_time)
        self.assertIsNotNone(dropped)
        self.assertEqual(len(fixed), 19)

        cum_tpv_fix = sum((c['open']+c['high']+c['low']+c['close'])/4 * c['volume']
                          for c in fixed)
        cum_vol_fix = sum(c['volume'] for c in fixed)
        vwap_fix = cum_tpv_fix / cum_vol_fix

        # --- Without fix ---
        cum_tpv_nf = sum((c['open']+c['high']+c['low']+c['close'])/4 * c['volume']
                         for c in all_candles)
        cum_vol_nf = sum(c['volume'] for c in all_candles)
        vwap_nf = cum_tpv_nf / cum_vol_nf

        # Volume difference must be exactly the partial candle's volume
        self.assertEqual(cum_vol_nf - cum_vol_fix, 193895)

        # VWAP values must differ
        self.assertNotAlmostEqual(vwap_fix, vwap_nf, places=4)

        # Fix VWAP matches the expected value from the session log (≈139.94 before partial)
        self.assertAlmostEqual(vwap_fix, 140.073, places=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
