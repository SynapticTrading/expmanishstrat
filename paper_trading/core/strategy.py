"""
Paper Trading Strategy - Intraday Momentum OI Unwinding
Same logic as backtest strategy but adapted for real-time execution
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, time
import pandas as pd
import numpy as np
from src.oi_analyzer import OIAnalyzer
from paper_trading.core.broker import PaperBroker


class IntradayMomentumOIPaper:
    """
    Paper trading implementation of Intraday Momentum OI strategy
    Uses same logic as backtest but with real-time data
    """

    def __init__(self, config, broker: PaperBroker, oi_analyzer: OIAnalyzer, state_manager=None, contract_manager=None, adapter=None, recorder=None):
        """
        Initialize strategy

        Args:
            config: Strategy configuration dict
            broker: PaperBroker instance
            oi_analyzer: OIAnalyzer instance
            state_manager: StateManager instance (optional)
            contract_manager: ContractManager instance (optional)
            adapter: BrokerAdapter instance for token-based lookups (optional)
            recorder: DataRecorder instance for persistent data storage (optional)
        """
        self.config = config
        self.broker = broker
        self.oi_analyzer = oi_analyzer
        self.state_manager = state_manager
        self.contract_manager = contract_manager
        self.adapter = adapter  # Broker adapter for unified interface
        self.recorder = recorder  # DataRecorder for persistent market data + VWAP storage

        # Extract config parameters
        entry_cfg = config['entry']
        exit_cfg = config['exit']
        market_cfg = config['market']
        risk_cfg = config['risk_management']

        # Entry parameters
        self.entry_start_time = self._parse_time(entry_cfg['start_time'])
        self.entry_end_time = self._parse_time(entry_cfg['end_time'])
        self.strikes_above_spot = entry_cfg['strikes_above_spot']
        self.strikes_below_spot = entry_cfg['strikes_below_spot']

        # Exit parameters
        self.exit_start_time = self._parse_time(exit_cfg['exit_start_time'])
        self.exit_end_time = self._parse_time(exit_cfg['exit_end_time'])
        self.initial_stop_loss_pct = exit_cfg['initial_stop_loss_pct']
        self.profit_threshold = exit_cfg['profit_threshold']
        self.trailing_stop_pct = exit_cfg['trailing_stop_pct']
        self.vwap_stop_pct = exit_cfg['vwap_stop_pct']
        self.oi_increase_stop_pct = exit_cfg['oi_increase_stop_pct']

        # Position sizing
        # Use contract manager lot size if available, otherwise fall back to config
        if self.contract_manager:
            self.lot_size = self.contract_manager.get_options_lot_size()
            print(f"[{datetime.now()}] Using lot size from contract manager: {self.lot_size} units/lot")
        else:
            self.lot_size = market_cfg['option_lot_size']
            print(f"[{datetime.now()}] Using lot size from config: {self.lot_size} units/lot")

        self.max_positions = risk_cfg['max_positions']

        # Daily state
        self.current_date = None
        self.daily_direction = None  # 'CALL' or 'PUT'
        self.daily_strike = None
        self.daily_expiry = None
        self.daily_trade_taken = False  # 1 trade per day limit
        self.max_call_oi_strike = None  # For state tracking
        self.max_put_oi_strike = None   # For state tracking

        # VWAP tracking: {(strike, option_type, expiry): {'tpv': float, 'volume': float}}
        self.vwap_running_totals = {}

        # Historical candles storage for VWAP initialization
        # Format: {(strike, option_type, expiry): [(timestamp, close, volume), ...]}
        self.historical_candles = {}
        self.historical_candles_max_size = 100  # Keep last 100 candles per strike

        print(f"[{datetime.now()}] Strategy initialized")
        print(f"  Entry: {self.entry_start_time} - {self.entry_end_time}")
        print(f"  Exit: {self.exit_start_time} - {self.exit_end_time}")
        print(f"  Stop Loss: {self.initial_stop_loss_pct*100:.1f}%")
        print(f"  Trailing Stop: {self.trailing_stop_pct*100:.1f}%")
        print(f"  VWAP Stop: {self.vwap_stop_pct*100:.1f}%")
        print(f"  OI Stop: {self.oi_increase_stop_pct*100:.1f}%")

    def _parse_time(self, time_str):
        """Parse time string to time object"""
        h, m = map(int, time_str.split(':'))
        return time(h, m)

    def _check_global_trades_today(self, current_time):
        """
        Check cumulative CSV for any trades today (from ANY broker AND any mode).
        This ensures 1 trade/day limit works globally across:
        - All brokers (Zerodha, AngelOne, etc.)
        - All modes (paper and live)

        Returns:
            int: Number of trades today across all brokers and modes
        """
        try:
            from pathlib import Path
            import pandas as pd

            logs_dir = Path(__file__).parent.parent / "logs"
            today = current_time.date()
            total_trades_today = 0

            # Check BOTH paper and live cumulative CSVs
            csv_files = [
                logs_dir / "trades_cumulative.csv",        # Paper trades
                logs_dir / "live_trades_cumulative.csv"    # Live trades
            ]

            for cumulative_csv in csv_files:
                if not cumulative_csv.exists():
                    continue

                try:
                    df = pd.read_csv(cumulative_csv)
                    if df.empty:
                        continue

                    # Parse entry_time and count trades from today
                    df['entry_date'] = pd.to_datetime(df['entry_time']).dt.date
                    trades = len(df[df['entry_date'] == today])
                    total_trades_today += trades

                    if trades > 0:
                        mode = "live" if "live_trades" in str(cumulative_csv) else "paper"
                        print(f"[{current_time}] 📊 Found {trades} {mode} trade(s) today in {cumulative_csv.name}")

                except Exception as e:
                    print(f"[{current_time}] ⚠️  Error reading {cumulative_csv.name}: {e}")
                    continue

            return total_trades_today

        except Exception as e:
            print(f"[{current_time}] ⚠️  Error checking global trades: {e}")
            return 0

    def on_new_day(self, current_time, spot_price, options_data):
        """
        Called at market open to determine daily direction

        Args:
            current_time: Current datetime
            spot_price: Current Nifty spot price
            options_data: DataFrame with current options data
        """
        current_date = current_time.date()

        # Reset if new day
        if self.current_date != current_date:
            print(f"\n{'='*80}")
            print(f"[{current_time}] NEW TRADING DAY: {current_date}")
            print(f"{'='*80}")

            self.current_date = current_date

            # Check for ANY trades today (from ANY broker via cumulative CSV)
            # This ensures 1 trade/day limit works globally, not per broker
            has_open_positions = len(self.broker.get_open_positions()) > 0
            has_closed_trades = len(self.broker.trade_history) > 0
            global_trades_today = self._check_global_trades_today(current_time)

            if has_open_positions:
                print(f"[{current_time}] ⚠️  Open positions detected - keeping daily_trade_taken = True")
            elif has_closed_trades:
                self.daily_trade_taken = True
                print(f"[{current_time}] ⚠️  Closed trades detected ({len(self.broker.trade_history)} trades) - setting daily_trade_taken = True")
            elif global_trades_today > 0:
                self.daily_trade_taken = True
                print(f"[{current_time}] ⚠️  Global trades detected ({global_trades_today} trade(s) today across all brokers) - setting daily_trade_taken = True")
            else:
                self.daily_trade_taken = False

            # Reset VWAP data for new day
            self.vwap_running_totals = {}
            self.historical_candles = {}
            print(f"[{current_time}] 🔄 Reset VWAP data and historical candles for new day")

            # Determine direction based on max OI buildup
            try:
                # Get expiry from first option in chain
                if not options_data.empty and 'expiry' in options_data.columns:
                    self.daily_expiry = options_data.iloc[0]['expiry']
                else:
                    print(f"[{current_time}] ✗ No expiry in options data")
                    self.daily_direction = None
                    return

                # Calculate max OI buildup from current options data (with debug logging)
                max_call_strike, max_put_strike, call_distance, put_distance = \
                    self.oi_analyzer.calculate_max_oi_buildup(options_data, spot_price, debug=True)

                # Store for state tracking
                self.max_call_oi_strike = max_call_strike
                self.max_put_oi_strike = max_put_strike

                if max_call_strike is None or max_put_strike is None:
                    print(f"[{current_time}] ✗ Could not determine max OI buildup")
                    self.daily_direction = None
                    return

                # Get actual OI values for the max strikes
                call_oi = options_data[
                    (options_data['strike'] == max_call_strike) &
                    (options_data['option_type'] == 'CE')
                ]['OI'].max()

                put_oi = options_data[
                    (options_data['strike'] == max_put_strike) &
                    (options_data['option_type'] == 'PE')
                ]['OI'].max()

                print(f"[{current_time}] Max Call OI: {call_oi:,.0f} @ {max_call_strike}, Max Put OI: {put_oi:,.0f} @ {max_put_strike}")

                # Determine direction
                self.daily_direction = self.oi_analyzer.determine_direction(call_distance, put_distance)

                if self.daily_direction is None:
                    print(f"[{current_time}] ✗ Could not determine direction")
                    return

                print(f"[{current_time}] Direction determined: {self.daily_direction} (Call dist: {call_distance:.2f}, Put dist: {put_distance:.2f})")

                # Get strike near spot for this direction
                strikes = options_data['strike'].unique()
                self.daily_strike = int(self.oi_analyzer.get_nearest_strike(
                    spot_price, self.daily_direction, strikes
                ))

                if self.daily_strike is None:
                    print(f"[{current_time}] ✗ Could not find suitable strike")
                    self.daily_direction = None
                    return

                print(f"[{current_time}] ✓ Daily Analysis Complete: Direction={self.daily_direction}, Strike={self.daily_strike}, Expiry={self.daily_expiry}, Spot={spot_price:.2f}")

                # Initialize VWAP with historical candles from 9:15 AM if started late
                from datetime import time as time_class
                if current_time.time() > time_class(9, 15):
                    self._initialize_vwap_from_market_open(current_time)
                    # Mark that we just initialized to avoid duplicate candle processing
                    self._skip_next_candle_fetch = True
                else:
                    self._skip_next_candle_fetch = False

                # Update strategy state
                if self.state_manager:
                    self.state_manager.update_strategy_state(
                        spot=spot_price,
                        strike=self.daily_strike,
                        direction=self.daily_direction,
                        call_strike=max_call_strike,
                        put_strike=max_put_strike,
                        vwap_tracking=self.vwap_running_totals,
                        expiry=self.daily_expiry
                    )
                    self.state_manager.save()

            except Exception as e:
                print(f"[{current_time}] ✗ Error determining direction: {e}")
                import traceback
                traceback.print_exc()
                self.daily_direction = None

    def on_candle(self, current_time, spot_price, options_data):
        """
        Called every 5 minutes with new candle data

        Args:
            current_time: Current datetime
            spot_price: Current Nifty spot price
            options_data: DataFrame with current options data
        """
        current_time_only = current_time.time()
        current_date = current_time.date()

        # Check if new day (9:15 AM)
        if current_time_only == time(9, 15):
            self.on_new_day(current_time, spot_price, options_data)

        # If started late and no direction set, determine it now
        elif self.current_date != current_date or self.daily_direction is None:
            print(f"\n{'='*80}")
            print(f"[{current_time}] ⚠️  STARTED LATE (after 9:15 AM)")
            print(f"[{current_time}] Determining direction using CURRENT OI data...")
            print(f"[{current_time}] (OI buildup direction is still valid mid-day)")
            print(f"{'='*80}\n")
            self.on_new_day(current_time, spot_price, options_data)

        # Check exit conditions for open positions
        self._check_exits(current_time, options_data)

        # Check entry conditions (only during entry window)
        if self.entry_start_time <= current_time_only <= self.entry_end_time:
            self._check_entry(current_time, spot_price, options_data)

        # Force exit at EOD
        if self.exit_start_time <= current_time_only <= self.exit_end_time:
            self._force_eod_exit(current_time, options_data)

        # Update strategy state (periodic update with current data)
        if self.state_manager and self.daily_direction:
            self.state_manager.update_strategy_state(
                spot=spot_price,
                strike=self.daily_strike,
                direction=self.daily_direction,
                call_strike=self.max_call_oi_strike,
                put_strike=self.max_put_oi_strike,
                vwap_tracking=self.vwap_running_totals,
                expiry=self.daily_expiry
            )
            self.state_manager.save()

    def _check_entry(self, current_time, spot_price, options_data):
        """Check if entry conditions are met (CANDLE-BASED with HLC/3 VWAP)"""

        # Skip if already have any open positions (only check entries when flat)
        if len(self.broker.get_open_positions()) > 0:
            return

        # Skip if no direction determined
        if not self.daily_direction or not self.daily_strike:
            return

        # ═══════════════════════════════════════════════════════════════
        # STEP 1: Calculate Strike Based on Current Spot
        # ═══════════════════════════════════════════════════════════════

        # Use available_strikes from metadata if provided, otherwise from options_data
        if hasattr(options_data, 'attrs') and 'available_strikes' in options_data.attrs:
            strikes = options_data.attrs['available_strikes']
        elif options_data is not None and not options_data.empty:
            strikes = options_data['strike'].unique()
        else:
            # Fallback: generate strikes around spot
            import numpy as np
            strikes = np.arange(int(spot_price) - 500, int(spot_price) + 500, 50)

        new_strike = self.oi_analyzer.get_nearest_strike(
            spot_price, self.daily_direction, strikes
        )

        if new_strike is not None:
            new_strike = int(new_strike)
        else:
            print(f"[{current_time}] ⚠️  Could not calculate strike for spot {spot_price:.2f}")
            return

        # ═══════════════════════════════════════════════════════════════
        # STEP 2: Check if Strike Changed → Fetch Historical Candles
        # ═══════════════════════════════════════════════════════════════

        if new_strike != self.daily_strike:
            old_strike = self.daily_strike
            self.daily_strike = new_strike
            print(f"[{current_time}] 📍 STRIKE UPDATED: {old_strike} → {new_strike} (Spot: {spot_price:.2f})")

            # Reset entry OI
            if hasattr(self, 'entry_oi'):
                delattr(self, 'entry_oi')

            # Clean up old strike's VWAP data
            vwap_keys_to_remove = [k for k in self.vwap_running_totals.keys() if k[0] == old_strike]
            for key in vwap_keys_to_remove:
                del self.vwap_running_totals[key]

            hist_keys_to_remove = [k for k in self.historical_candles.keys() if k[0] == old_strike]
            for key in hist_keys_to_remove:
                del self.historical_candles[key]

            if vwap_keys_to_remove or hist_keys_to_remove:
                print(f"[{current_time}] 🧹 Cleaned up old strike {old_strike} data")

            # ╔═════════════════════════════════════════════════════════════╗
            # ║ FETCH HISTORICAL CANDLES FOR NEW STRIKE (from 9:15 AM)     ║
            # ╚═════════════════════════════════════════════════════════════╝

            from datetime import time as time_class
            if self.adapter and current_time.time() > time_class(9, 15):
                print(f"[{current_time}] 📥 Fetching historical candles from 9:15 AM for {self.daily_direction} {new_strike}...")

                market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)

                # Convert CALL/PUT to CE/PE for adapter
                option_type_code = 'CE' if self.daily_direction == 'CALL' else 'PE'

                try:
                    historical_candles = self.adapter.get_historical_candles(
                        underlying="NIFTY",
                        option_type=option_type_code,
                        strike=new_strike,
                        expiry=self.daily_expiry,
                        from_time=market_open,
                        to_time=current_time
                    )

                    if historical_candles:
                        print(f"[{current_time}] ✓ Fetched {len(historical_candles)} historical candles")

                        # Initialize VWAP with historical candles (HLC/3 formula)
                        success = self._initialize_vwap_with_history(
                            new_strike,
                            self.daily_direction,
                            self.daily_expiry,
                            historical_candles
                        )

                        if success:
                            self._store_historical_candles_bulk(
                                new_strike,
                                self.daily_direction,
                                self.daily_expiry,
                                historical_candles
                            )
                            self.vwap_initialized = True

                            # Use the last historical candle as the current candle
                            # (avoids duplicate processing)
                            last_candle = historical_candles[-1]
                            current_candle = {
                                'open': last_candle['open'],
                                'high': last_candle['high'],
                                'low': last_candle['low'],
                                'close': last_candle['close'],
                                'volume': last_candle['volume'],
                                'oi': last_candle.get('oi', 0)  # Use OI from candle if available
                            }

                            # Fetch OI via quote API if not in candle (AngelOne always needs this)
                            if current_candle['oi'] == 0:
                                current_candle['oi'] = self._fetch_oi_for_strike(
                                    new_strike,
                                    'CE' if self.daily_direction == 'CALL' else 'PE',
                                    self.daily_expiry
                                )

                            # Store the candle for use in STEP 3 (avoids re-fetch)
                            self._last_initialized_candle = current_candle

                            # Skip the normal current candle fetch (already have it from historical)
                            skip_current_candle_fetch = True
                        else:
                            print(f"[{current_time}] ⚠️  Failed to initialize VWAP with historical data")
                            skip_current_candle_fetch = False
                    else:
                        print(f"[{current_time}] ⚠️  No historical candles available for {self.daily_direction} {new_strike}")
                        skip_current_candle_fetch = False

                except Exception as e:
                    print(f"[{current_time}] ✗ Error fetching historical candles: {e}")
                    import traceback
                    traceback.print_exc()
                    skip_current_candle_fetch = False
            else:
                skip_current_candle_fetch = False
        else:
            skip_current_candle_fetch = False

        # ═══════════════════════════════════════════════════════════════
        # STEP 3: Fetch Current Candle for Selected Strike
        # ═══════════════════════════════════════════════════════════════

        # Check if we should skip (either from strike update or from on_new_day initialization)
        should_skip = skip_current_candle_fetch or getattr(self, '_skip_next_candle_fetch', False)

        if should_skip:
            # Use the last candle from historical initialization
            if hasattr(self, '_last_initialized_candle'):
                current_candle = self._last_initialized_candle

                # Fetch OI if not already set (e.g. on_new_day init path)
                if current_candle['oi'] == 0:
                    current_candle['oi'] = self._fetch_oi_for_strike(
                        self.daily_strike,
                        'CE' if self.daily_direction == 'CALL' else 'PE',
                        self.daily_expiry
                    )

                # Clear the stored candle
                delattr(self, '_last_initialized_candle')
            else:
                print(f"[{current_time}] ⚠️  No stored candle from initialization")
                return

        # Clear the skip flag after checking
        if hasattr(self, '_skip_next_candle_fetch'):
            self._skip_next_candle_fetch = False

        if not should_skip:
            current_candle = self._fetch_current_strike_candle(
                self.daily_strike,
                self.daily_direction,
                self.daily_expiry,
                current_time
            )

            if not current_candle:
                print(f"[{current_time}] ⚠️  Could not fetch current candle for {self.daily_direction} {self.daily_strike}")
                return

        # Extract OHLCV data
        ohlc_data = {
            'open': current_candle['open'],
            'high': current_candle['high'],
            'low': current_candle['low'],
            'close': current_candle['close']
        }
        option_volume = current_candle['volume']
        option_oi = current_candle['oi']
        option_price = current_candle['close']  # For entry price comparison

        # ═══════════════════════════════════════════════════════════════
        # STEP 4: Calculate VWAP using HLC/3 Formula
        # ═══════════════════════════════════════════════════════════════

        # Only update VWAP if we fetched a new candle (not using stored historical candle)
        if should_skip:
            # VWAP already initialized with historical data - just retrieve it
            key = (self.daily_strike, self.daily_direction, self.daily_expiry)
            if key in self.vwap_running_totals and self.vwap_running_totals[key]['volume'] > 0:
                vwap = self.vwap_running_totals[key]['tpv'] / self.vwap_running_totals[key]['volume']
            else:
                vwap = None
        else:
            # Update VWAP with new candle
            vwap = self._calculate_vwap_ohlc(
                self.daily_strike,
                self.daily_direction,
                self.daily_expiry,
                ohlc_data,
                option_volume
            )

        # Log VWAP initialization (first time only)
        if vwap and not getattr(self, 'vwap_initialized', False):
            print(f"[{current_time}] 🎯 VWAP initialized for {self.daily_direction} {self.daily_strike}: ₹{vwap:.2f}")
            self.vwap_initialized = True

        # ═══════════════════════════════════════════════════════════════
        # STEP 5: Calculate OI Change and Check Entry Conditions
        # ═══════════════════════════════════════════════════════════════

        # Calculate OI change vs baseline (set when strike is first established/updated)
        if hasattr(self, 'entry_oi'):
            oi_change = option_oi - self.entry_oi
            oi_change_pct = (oi_change / self.entry_oi * 100) if self.entry_oi > 0 else 0
        else:
            # First candle for this strike - record as baseline, no signal yet
            self.entry_oi = option_oi
            oi_change_pct = 0
            oi_change = 0

        # Check entry conditions
        is_unwinding = oi_change_pct < 0  # OI unwinding (decreasing)
        price_above_vwap = option_price > vwap if vwap else False

        # Detailed logging
        print(f"[{current_time}] Checking entry: {self.daily_direction} {self.daily_strike}, Expiry={self.daily_expiry}")

        oi_status = "UNWINDING ✓" if is_unwinding else "BUILDING"
        print(f"[{current_time}] {self.daily_direction} {self.daily_strike}: OI={option_oi:,.0f}, Change={oi_change:,.0f} ({oi_change_pct:+.2f}%) - {oi_status}")

        if vwap:
            vwap_status = "ABOVE ✓" if price_above_vwap else "BELOW ✗"
            print(f"[{current_time}] {self.daily_direction} {self.daily_strike}: Price=₹{option_price:.2f}, VWAP=₹{vwap:.2f} - {vwap_status}")

        # Enter trade if conditions met
        if is_unwinding and price_above_vwap:
            print(f"[{current_time}] 🎯 ENTRY SIGNAL: {self.daily_direction} {self.daily_strike} - Price: {option_price:.2f}, VWAP: {vwap:.2f}, OI Change: {oi_change:,.0f} ({oi_change_pct:.2f}%)")

            if self.daily_trade_taken:
                print(f"[{current_time}] ⛔ Entry blocked: Daily trade limit reached (1 trade/day)")
                return

            print(f"[{current_time}] 📈 PLACING BUY ORDER: size=1, expected_price={option_price:.2f}")

            position = self.broker.buy(
                strike=self.daily_strike,
                option_type=self.daily_direction,
                expiry=self.daily_expiry,
                price=option_price,
                size=self.lot_size,
                vwap=vwap,
                oi=option_oi,
                oi_change=oi_change_pct
            )

            if position:
                self.daily_trade_taken = True
                print(f"[{current_time}] 🔵 BUY OPTION EXECUTED: {self.daily_direction} {self.daily_strike} @ ₹{option_price:.2f} (Expiry: {self.daily_expiry}, 1 lot = {self.lot_size} qty)")
                print(f"[{current_time}]    📊 ENTRY DATA: VWAP={vwap:.2f}, OI={option_oi:,.0f}, OI Change={oi_change:,.0f} ({oi_change_pct:.2f}%)")

    def _update_vwap_for_positions(self, current_time):
        """
        Fetch the latest completed 5-min candle for each open position and update VWAP.
        Called once per 5-min boundary from the 1-min exit monitor loop.
        """
        positions = self.broker.get_open_positions()
        for position in positions:
            try:
                candle = self._fetch_current_strike_candle(
                    position.strike,
                    position.option_type,
                    position.expiry,
                    current_time
                )
                if not candle:
                    continue
                ohlc_data = {
                    'open':  candle['open'],
                    'high':  candle['high'],
                    'low':   candle['low'],
                    'close': candle['close']
                }
                self._calculate_vwap_ohlc(
                    position.strike,
                    position.option_type,
                    position.expiry,
                    ohlc_data,
                    candle['volume']
                )
            except Exception as e:
                print(f"[{current_time}] ⚠️  VWAP update failed for {position.strike} {position.option_type}: {e}")

    def _get_current_vwap(self, strike, option_type, expiry):
        """Return current VWAP from cached running totals without updating it."""
        key = (strike, option_type, expiry)
        if key in self.vwap_running_totals:
            totals = self.vwap_running_totals[key]
            if totals.get('volume', 0) > 0:
                return totals['tpv'] / totals['volume']
        return None

    def _check_exits(self, current_time, options_data, use_ltp_only=False):
        """Check exit conditions for all open positions.

        Args:
            use_ltp_only: When True (1-min LTP loop), use LTP already present in
                          options_data instead of fetching historical candles.
                          VWAP is read from cache and NOT updated.
                          When False (5-min strategy loop), fetch a fresh candle
                          and update VWAP as normal.
        """

        positions = self.broker.get_open_positions()

        if not positions:
            return

        for position in positions.copy():  # Use copy to avoid modification during iteration

            if use_ltp_only:
                # ── 1-min LTP path: use pre-fetched quote, skip candle API call ──
                option_type_code = 'PE' if position.option_type in ('PUT', 'PE') else 'CE'
                strike = int(position.strike)

                row = None
                if options_data is not None and not options_data.empty:
                    mask = (
                        (options_data['strike'] == strike) &
                        (options_data['option_type'] == option_type_code)
                    )
                    matching = options_data[mask]
                    if not matching.empty:
                        row = matching.iloc[0]

                if row is None:
                    print(f"[{current_time}] ⚠️  LTP not found in options_data for {strike} {option_type_code}, skipping")
                    continue

                current_price = float(row['close'])   # actual current LTP
                current_oi    = float(row['OI'])

                # Use cached VWAP — do NOT update it (only 5-min candles update VWAP)
                vwap = self._get_current_vwap(position.strike, position.option_type, position.expiry)

            else:
                # ── 5-min candle path: fetch fresh candle and update VWAP ──
                try:
                    current_candle = self._fetch_current_strike_candle(
                        position.strike,
                        position.option_type,
                        position.expiry,
                        current_time
                    )
                except Exception as e:
                    print(f"[{current_time}] ⚠️  Could not fetch candle for {position.strike} {position.option_type}: {e}")
                    continue

                if not current_candle:
                    print(f"[{current_time}] ⚠️  No candle data for {position.strike} {position.option_type}")
                    continue

                current_price  = current_candle['close']
                current_oi     = current_candle['oi']
                current_volume = current_candle['volume']

                ohlc_data = {
                    'open':  current_candle['open'],
                    'high':  current_candle['high'],
                    'low':   current_candle['low'],
                    'close': current_candle['close']
                }

                vwap = self._calculate_vwap_ohlc(
                    position.strike,
                    position.option_type,
                    position.expiry,
                    ohlc_data,
                    current_volume
                )

            # Check for EOD exit FIRST (priority exit)
            current_time_only = current_time.time()
            if self.exit_start_time <= current_time_only <= self.exit_end_time:
                print(f"[{current_time}] 🔔 END OF DAY EXIT TIME - Forcing exit")
                self.broker.sell(position, current_price, vwap, current_oi, "EOD Exit")
                continue  # Skip to next position

            # Calculate P&L
            pnl_pct = (current_price / position.entry_price - 1)

            # Update peak for trailing stop
            if current_price > position.peak_price:
                position.peak_price = current_price

            # Check if profit threshold reached for trailing stop
            if current_price >= position.entry_price * self.profit_threshold:
                if not position.trailing_stop_active:
                    position.trailing_stop_active = True
                    print(f"[{current_time}] 🎯 Trailing stop ACTIVATED for {position.strike} {position.option_type}")

            # Update state file with current position data
            if self.state_manager and hasattr(position, 'order_id'):
                self.state_manager.update_position_price(
                    order_id=position.order_id,
                    current_price=current_price,
                    vwap=vwap,
                    oi=current_oi,
                    peak_price=position.peak_price,
                    trailing_stop_active=position.trailing_stop_active
                )

            # Calculate all stop loss levels
            stop_loss_price = position.entry_price * (1 - self.initial_stop_loss_pct)

            # Log current status
            print(f"[{current_time}] 📊 LTP CHECK: {position.strike} {position.option_type}")
            print(f"    Current LTP: ₹{current_price:.2f} | Entry: ₹{position.entry_price:.2f} | P&L: {pnl_pct*100:+.2f}%")
            print(f"    Initial Stop: ₹{stop_loss_price:.2f} (distance: {((current_price/stop_loss_price - 1)*100):.2f}%)")

            # VWAP stop info (only in loss)
            if pnl_pct < 0 and vwap:
                vwap_stop_price = vwap * (1 - self.vwap_stop_pct)
                print(f"    VWAP Stop: ₹{vwap_stop_price:.2f} | Current VWAP: ₹{vwap:.2f}")

            # OI change info (only in loss)
            if pnl_pct < 0 and position.oi_at_entry > 0:
                oi_change_pct = (current_oi / position.oi_at_entry - 1)
                print(f"    OI Change: {oi_change_pct*100:+.2f}% (Threshold: {self.oi_increase_stop_pct*100:.0f}%)")

            # Trailing stop info (if active)
            if position.trailing_stop_active:
                trailing_stop_price = position.peak_price * (1 - self.trailing_stop_pct)
                print(f"    🎯 Trailing: Active | Peak: ₹{position.peak_price:.2f} | Stop: ₹{trailing_stop_price:.2f}")

            exit_reason = None

            if position.trailing_stop_active:
                trailing_stop_price = position.peak_price * (1 - self.trailing_stop_pct)

                if pnl_pct >= 0:
                    # In profit: only trailing stop fires
                    if current_price <= trailing_stop_price:
                        exit_reason = f"Trailing Stop ({self.trailing_stop_pct*100:.0f}%)"
                else:
                    # In loss: collect all triggered price-based stops, pick highest (= least loss)
                    triggered = []

                    if current_price <= trailing_stop_price:
                        triggered.append((trailing_stop_price, f"Trailing Stop ({self.trailing_stop_pct*100:.0f}%)"))

                    if current_price <= stop_loss_price:
                        triggered.append((stop_loss_price, f"Stop Loss ({self.initial_stop_loss_pct*100:.0f}%)"))

                    if vwap:
                        vwap_stop_price = vwap * (1 - self.vwap_stop_pct)
                        if current_price <= vwap_stop_price:
                            triggered.append((vwap_stop_price, f"VWAP Stop (>{self.vwap_stop_pct*100:.0f}% below VWAP)"))

                    if triggered:
                        # Highest stop price = would have fired first = least loss
                        exit_reason = max(triggered, key=lambda x: x[0])[1]
                    else:
                        # No price-based stop triggered — check OI stop as fallback
                        if position.oi_at_entry > 0:
                            oi_change_pct = (current_oi / position.oi_at_entry - 1)
                            if oi_change_pct > self.oi_increase_stop_pct:
                                exit_reason = f"OI Increase Stop ({oi_change_pct*100:+.1f}%)"

            else:
                # Trailing not active — use normal stop priority
                # 1. Initial stop loss (25%)
                if current_price <= stop_loss_price:
                    exit_reason = f"Stop Loss ({self.initial_stop_loss_pct*100:.0f}%)"

                # 2. Loss-based stops: VWAP stop, then OI increase stop
                elif pnl_pct < 0:
                    if vwap:
                        vwap_stop_price = vwap * (1 - self.vwap_stop_pct)
                        if current_price <= vwap_stop_price:
                            exit_reason = f"VWAP Stop (>{self.vwap_stop_pct*100:.0f}% below VWAP)"

                    # 3. OI increase stop (only if VWAP stop didn't fire)
                    if not exit_reason and position.oi_at_entry > 0:
                        oi_change_pct = (current_oi / position.oi_at_entry - 1)
                        if oi_change_pct > self.oi_increase_stop_pct:
                            exit_reason = f"OI Increase Stop ({oi_change_pct*100:+.1f}%)"

            # Execute exit if reason found
            if exit_reason:
                print(f"[{current_time}] EXIT SIGNAL: {exit_reason}")
                self.broker.sell(position, current_price, vwap, current_oi, exit_reason)

    def _force_eod_exit(self, current_time, options_data):
        """Force exit all positions at end of day (CANDLE-BASED with HLC/3 VWAP)"""

        positions = self.broker.get_open_positions()

        if positions:
            print(f"[{current_time}] Forcing EOD exit for {len(positions)} position(s)")

            for position in positions.copy():
                # Fetch current candle for this position's strike (CANDLE-BASED)
                try:
                    current_candle = self._fetch_current_strike_candle(
                        position.strike,
                        position.option_type,
                        position.expiry,
                        current_time
                    )
                except Exception as e:
                    print(f"[{current_time}] ⚠️  Could not fetch candle for EOD exit {position.strike} {position.option_type}: {e}")
                    continue

                current_price = current_candle['close']
                current_oi = current_candle['oi']
                current_volume = current_candle['volume']

                # Extract OHLC data for OHLC/4 VWAP calculation (same as entry)
                ohlc_data = {
                    'open': current_candle['open'],
                    'high': current_candle['high'],
                    'low': current_candle['low'],
                    'close': current_candle['close']
                }

                vwap = self._calculate_vwap_ohlc(
                    position.strike,
                    position.option_type,
                    position.expiry,
                    ohlc_data,
                    current_volume
                )

                self.broker.sell(position, current_price, vwap, current_oi, "EOD Exit")

    def _get_option_data(self, options_data, strike, option_type, expiry):
        """Get option data for specific strike/type/expiry"""

        try:
            # Map CALL/PUT to CE/PE (to match data format from broker)
            if option_type == 'CALL':
                option_type_filter = 'CE'
            elif option_type == 'PUT':
                option_type_filter = 'PE'
            else:
                option_type_filter = option_type  # Already CE/PE

            # Convert expiry to comparable format (handle string vs date object)
            import pandas as pd
            from datetime import date

            # If expiry is None, get it from options_data (from contracts_cache.json)
            if expiry is None and not options_data.empty and 'expiry' in options_data.columns:
                expiry = options_data.iloc[0]['expiry']

            # Normalize expiry to date object
            if isinstance(expiry, str):
                expiry_date = pd.to_datetime(expiry).date()
            elif isinstance(expiry, pd.Timestamp):
                expiry_date = expiry.date()
            elif isinstance(expiry, date):
                expiry_date = expiry
            else:
                expiry_date = expiry

            # Normalize options_data expiry column
            options_expiry = options_data['expiry']
            if len(options_expiry) > 0:
                first_val = options_expiry.iloc[0]
                if isinstance(first_val, pd.Timestamp):
                    options_data_expiry = options_expiry.dt.date
                elif isinstance(first_val, date):
                    options_data_expiry = options_expiry
                else:
                    options_data_expiry = pd.to_datetime(options_expiry).dt.date

            mask = (
                (options_data['strike'] == strike) &
                (options_data['option_type'] == option_type_filter) &
                (options_data_expiry == expiry_date)
            )
            data = options_data[mask]

            if len(data) == 0:
                return None

            return data.iloc[0]

        except Exception as e:
            print(f"Error getting option data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _store_historical_candle(self, strike, option_type, expiry, timestamp, close, volume):
        """
        Store historical candle data for VWAP backfilling.

        Args:
            strike: Strike price
            option_type: CALL or PUT
            expiry: Expiry date
            timestamp: Candle timestamp
            close: Close price
            volume: Cumulative volume
        """
        key = (strike, option_type, expiry)

        if key not in self.historical_candles:
            self.historical_candles[key] = []

        # Store candle data as tuple: (timestamp, close, volume)
        self.historical_candles[key].append((timestamp, close, volume))

        # Limit history size to prevent memory bloat
        if len(self.historical_candles[key]) > self.historical_candles_max_size:
            self.historical_candles[key].pop(0)  # Remove oldest

    def _store_historical_candles_bulk(self, strike, option_type, expiry, candles):
        """
        Store multiple historical candles at once (for strike initialization).

        Args:
            strike: Strike price
            option_type: CALL or PUT
            expiry: Expiry date
            candles: List of candle dicts from adapter (with OHLCV data)
        """
        if not candles:
            return

        key = (strike, option_type, expiry)

        if key not in self.historical_candles:
            self.historical_candles[key] = []

        # Store all candles
        for candle in candles:
            self.historical_candles[key].append((
                candle['timestamp'],
                candle['close'],
                candle['volume']
            ))

        # Limit size to prevent memory bloat
        if len(self.historical_candles[key]) > self.historical_candles_max_size:
            # Keep only the most recent candles
            self.historical_candles[key] = self.historical_candles[key][-self.historical_candles_max_size:]

        print(f"[{datetime.now()}] 📦 Stored {len(candles)} historical candles for {option_type} {strike}")

    def _initialize_vwap_from_market_open(self, current_time):
        """
        Initialize VWAP with historical candles from 9:15 AM (market open).

        Called when direction is first determined (especially when starting late).
        Fetches all candles from market open to now and initializes VWAP.

        Args:
            current_time: Current datetime
        """
        if not self.adapter or not self.daily_direction or not self.daily_strike:
            return

        print(f"[{current_time}] 📥 Fetching historical candles from 9:15 AM for {self.daily_direction} {self.daily_strike}...")

        market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)

        # Convert CALL/PUT to CE/PE for adapter
        option_type_code = 'CE' if self.daily_direction == 'CALL' else 'PE'

        try:
            historical_candles = self.adapter.get_historical_candles(
                underlying="NIFTY",
                option_type=option_type_code,
                strike=self.daily_strike,
                expiry=self.daily_expiry,
                from_time=market_open,
                to_time=current_time
            )

            if historical_candles:
                num_candles = len(historical_candles)
                print(f"[{current_time}] ✓ Fetched {num_candles} historical candles from 9:15 AM")

                # Drop the last candle if it is still in progress.
                # The broker returns the current incomplete candle (e.g. started at 10:50,
                # fetched at 10:51 — only 1 min of data). Including it here would
                # double-count it when the live_update adds the completed version at 10:55.
                from datetime import timedelta
                if historical_candles:
                    last_candle = historical_candles[-1]
                    last_ts = last_candle.get('timestamp')
                    if last_ts is not None:
                        # Candle is complete only when candle_time + 5 min <= current_time
                        # Normalise both to naive IST for comparison (handles all broker combinations)
                        import pytz
                        ist = pytz.timezone('Asia/Kolkata')

                        def _to_naive_ist(dt):
                            if dt.tzinfo is not None:
                                return dt.astimezone(ist).replace(tzinfo=None)
                            return dt

                        last_ts_naive = _to_naive_ist(last_ts)
                        current_time_naive = _to_naive_ist(current_time)
                        if last_ts_naive + timedelta(minutes=5) > current_time_naive:
                            dropped = historical_candles[-1]
                            historical_candles = historical_candles[:-1]
                            print(f"[{current_time}] ⚠️  Dropped incomplete last candle: "
                                  f"{dropped.get('timestamp')} (still in progress, vol={dropped.get('volume', 0):,})")

                if not historical_candles:
                    print(f"[{current_time}] ⚠️  No complete candles to initialize VWAP")
                    return

                print(f"[{current_time}] 🎯 Initializing VWAP with {len(historical_candles)} complete candles")

                # Initialize VWAP with historical candles (HLC/3 formula)
                success = self._initialize_vwap_with_history(
                    self.daily_strike,
                    self.daily_direction,
                    self.daily_expiry,
                    historical_candles
                )

                if success:
                    # Also store the candles for reference
                    self._store_historical_candles_bulk(
                        self.daily_strike,
                        self.daily_direction,
                        self.daily_expiry,
                        historical_candles
                    )
                    print(f"[{current_time}] 🎯 Initialized VWAP for {self.daily_direction} {self.daily_strike}: {num_candles} bars from 9:15 AM")

                    # Store the last candle for use in _check_entry (avoid duplicate fetch)
                    last_candle = historical_candles[-1]
                    oi = last_candle.get('oi', 0)
                    if oi == 0:
                        # AngelOne candles have no OI — fetch via quote API now so
                        # STEP 3 in _check_entry doesn't need a separate call
                        option_type_code = 'CE' if self.daily_direction == 'CALL' else 'PE'
                        oi = self._fetch_oi_for_strike(self.daily_strike, option_type_code, self.daily_expiry)
                    self._last_initialized_candle = {
                        'open': last_candle['open'],
                        'high': last_candle['high'],
                        'low': last_candle['low'],
                        'close': last_candle['close'],
                        'volume': last_candle['volume'],
                        'oi': oi
                    }
                else:
                    print(f"[{current_time}] ⚠️  Failed to initialize VWAP with historical data")
            else:
                print(f"[{current_time}] ⚠️  No historical candles available from 9:15 AM")

        except Exception as e:
            print(f"[{current_time}] ✗ Error fetching historical candles: {e}")
            import traceback
            traceback.print_exc()

    def _initialize_vwap_with_history(self, strike, option_type, expiry, candles_data):
        """
        Initialize VWAP with historical candles using HLC/3 formula.

        Args:
            strike: Strike price
            option_type: CALL or PUT
            expiry: Expiry date
            candles_data: List of candle dicts with OHLCV data (from adapter)

        Returns:
            bool: True if initialized successfully
        """
        if not candles_data:
            return False

        key = (strike, option_type, expiry)

        # Initialize VWAP state
        self.vwap_running_totals[key] = {
            'tpv': 0.0,
            'volume': 0.0,
            'prev_cumulative_volume': 0.0
        }

        print(f"[{datetime.now()}] 🔄 Initializing VWAP for {option_type} {strike} with {len(candles_data)} historical candles")

        # Detect if volume is cumulative or interval by checking multiple candles
        # Check first 10 candles (or all if less) for decreasing volume
        is_interval_volume = False
        if len(candles_data) > 1:
            # Check up to first 10 candles for any decrease in volume
            check_count = min(10, len(candles_data))
            decreases_found = 0

            for i in range(1, check_count):
                if candles_data[i]['volume'] < candles_data[i-1]['volume']:
                    decreases_found += 1

            # If we find ANY decreases, it's interval volume
            if decreases_found > 0:
                is_interval_volume = True
                print(f"[{datetime.now()}] ℹ️  Detected INTERVAL volume (per-candle) - found {decreases_found} decrease(s) in first {check_count} candles")
            else:
                print(f"[{datetime.now()}] ℹ️  Detected CUMULATIVE volume (from market open) - no decreases in first {check_count} candles")

        # Persist the volume type so ongoing updates use the same logic
        self.vwap_running_totals[key]['is_interval_volume'] = is_interval_volume

        # Record the full candle fetch to persistent store (once, before loop)
        if self.recorder:
            self.recorder.record_candle_fetch(
                fetch_reason='vwap_init',
                strike=strike,
                option_type=option_type if option_type in ('CE', 'PE') else ('CE' if option_type == 'CALL' else 'PE'),
                expiry=expiry,
                from_time=candles_data[0].get('timestamp') if candles_data else None,
                to_time=candles_data[-1].get('timestamp') if candles_data else None,
                candles=candles_data
            )

        # Backfill VWAP with each historical candle using OHLC/4 formula
        debug_first_3 = []
        debug_last_3 = []

        for idx, candle in enumerate(candles_data):
            # Calculate typical price using OHLC/4 formula (more accurate than HLC/3)
            typical_price = (candle['open'] + candle['high'] + candle['low'] + candle['close']) / 4

            # Calculate incremental volume based on type
            if is_interval_volume:
                # Volume is already per-candle, use it directly
                incremental_volume = candle['volume']
            else:
                # Volume is cumulative, calculate the delta
                prev_cumul = self.vwap_running_totals[key]['prev_cumulative_volume']
                incremental_volume = candle['volume'] - prev_cumul
                self.vwap_running_totals[key]['prev_cumulative_volume'] = candle['volume']

            # Capture state BEFORE update for recorder
            cum_tpv_before = self.vwap_running_totals[key]['tpv']
            cum_vol_before = self.vwap_running_totals[key]['volume']

            # Accumulate TPV
            tpv_added = typical_price * incremental_volume
            self.vwap_running_totals[key]['tpv'] += tpv_added
            self.vwap_running_totals[key]['volume'] += incremental_volume

            # Record this VWAP init step with full before/after state
            if self.recorder:
                self.recorder.record_vwap_step(
                    step_type='init_candle',
                    strike=strike,
                    option_type=option_type if option_type in ('CE', 'PE') else ('CE' if option_type == 'CALL' else 'PE'),
                    expiry=expiry,
                    candle_time=candle.get('timestamp'),
                    ohlc={'open': candle['open'], 'high': candle['high'],
                          'low': candle['low'], 'close': candle['close']},
                    raw_volume=candle['volume'],
                    is_interval_volume=is_interval_volume,
                    incremental_volume=incremental_volume,
                    cum_tpv_before=cum_tpv_before,
                    cum_volume_before=cum_vol_before,
                    cum_tpv_after=self.vwap_running_totals[key]['tpv'],
                    cum_volume_after=self.vwap_running_totals[key]['volume']
                )

            # Debug: Store first 3 and last 3 candles
            candle_info = {
                'idx': idx,
                'time': candle.get('timestamp', 'N/A'),
                'ohlc4': f"₹{typical_price:.2f}",
                'vol': incremental_volume,
                'o': candle['open'],
                'h': candle['high'],
                'l': candle['low'],
                'c': candle['close']
            }
            if idx < 3:
                debug_first_3.append(candle_info)
            if idx >= len(candles_data) - 3:
                debug_last_3.append(candle_info)

        # Calculate and log the initialized VWAP
        if self.vwap_running_totals[key]['volume'] > 0:
            vwap = self.vwap_running_totals[key]['tpv'] / self.vwap_running_totals[key]['volume']
            total_tpv = self.vwap_running_totals[key]['tpv']
            total_vol = self.vwap_running_totals[key]['volume']

            print(f"[{datetime.now()}] ✓ Initialized VWAP: ₹{vwap:.2f} (using {len(candles_data)} candles with OHLC/4 formula)")
            print(f"[{datetime.now()}] 📊 VWAP Debug: TPV={total_tpv:,.0f}, Volume={total_vol:,.0f}")

            # Print first 3 candles
            print(f"[{datetime.now()}] 🔍 First 3 candles:")
            for c in debug_first_3:
                print(f"   [{c['idx']}] {c['time']} → OHLC4={c['ohlc4']} (O={c['o']}, H={c['h']}, L={c['l']}, C={c['c']}), Vol={c['vol']:,}")

            # Print last 3 candles
            print(f"[{datetime.now()}] 🔍 Last 3 candles:")
            for c in debug_last_3:
                print(f"   [{c['idx']}] {c['time']} → OHLC4={c['ohlc4']} (O={c['o']}, H={c['h']}, L={c['l']}, C={c['c']}), Vol={c['vol']:,}")

            return True

        return False

    def _calculate_vwap(self, strike, option_type, expiry, price, volume):
        """
        Calculate incremental VWAP for option using cumulative volume.

        Handles both candle-based (interval volume) and quote-based (cumulative volume) data.
        For cumulative volume, calculates incremental delta to avoid double-counting.

        Args:
            strike: Strike price
            option_type: CALL or PUT
            expiry: Expiry date
            price: Current price (LTP or candle close)
            volume: Current volume (cumulative from market open, or interval volume)

        Returns:
            float: VWAP value
        """
        key = (strike, option_type, expiry)

        # Initialize if first time - try to backfill with historical data
        if key not in self.vwap_running_totals:
            # Try to initialize with historical candles
            initialized_with_history = self._initialize_vwap_with_history(
                strike, option_type, expiry, datetime.now()
            )

            # If no historical data available, initialize with zeros
            if not initialized_with_history:
                self.vwap_running_totals[key] = {
                    'tpv': 0.0,                      # Total Price × Volume
                    'volume': 0.0,                   # Total Volume
                    'prev_cumulative_volume': 0.0    # Track previous cumulative volume
                }

        # Calculate incremental volume (delta since last update)
        # This handles cumulative volume from quote data
        prev_cumulative = self.vwap_running_totals[key]['prev_cumulative_volume']
        incremental_volume = volume - prev_cumulative

        # Update running totals with INCREMENTAL volume only
        self.vwap_running_totals[key]['tpv'] += price * incremental_volume
        self.vwap_running_totals[key]['volume'] += incremental_volume

        # Store current cumulative volume for next iteration
        self.vwap_running_totals[key]['prev_cumulative_volume'] = volume

        # Calculate VWAP
        if self.vwap_running_totals[key]['volume'] > 0:
            vwap = self.vwap_running_totals[key]['tpv'] / self.vwap_running_totals[key]['volume']
            return vwap
        else:
            return price  # Fallback to current price if no volume

    def _calculate_vwap_ohlc(self, strike, option_type, expiry, ohlc_data, volume):
        """
        Calculate VWAP using OHLC/4 (Open + High + Low + Close) / 4 formula.

        Args:
            strike: Strike price
            option_type: CALL or PUT
            expiry: Expiry date
            ohlc_data: Dict with {open, high, low, close}
            volume: Cumulative volume from market open

        Returns:
            float: VWAP value
        """
        key = (strike, option_type, expiry)

        # Initialize if first time (and not already initialized with historical data)
        if key not in self.vwap_running_totals:
            # Single-candle fetches always return interval (per-candle) volume
            self.vwap_running_totals[key] = {
                'tpv': 0.0,
                'volume': 0.0,
                'prev_cumulative_volume': 0.0,
                'is_interval_volume': True
            }

        # Calculate typical price using OHLC/4 formula (more accurate)
        typical_price = (ohlc_data['open'] + ohlc_data['high'] + ohlc_data['low'] + ohlc_data['close']) / 4

        # Determine incremental volume based on how the broker reports it
        is_interval = self.vwap_running_totals[key].get('is_interval_volume', True)
        if is_interval:
            # Volume is per-candle (interval) — use it directly; no delta needed
            incremental_volume = volume
        else:
            # Volume is cumulative from market open — compute the delta to avoid double-counting
            prev_cumulative = self.vwap_running_totals[key]['prev_cumulative_volume']
            incremental_volume = volume - prev_cumulative
            self.vwap_running_totals[key]['prev_cumulative_volume'] = volume

        # Capture state BEFORE update for recorder
        cum_tpv_before = self.vwap_running_totals[key]['tpv']
        cum_vol_before = self.vwap_running_totals[key]['volume']

        # Update running totals
        self.vwap_running_totals[key]['tpv'] += typical_price * incremental_volume
        self.vwap_running_totals[key]['volume'] += incremental_volume

        # Record this live VWAP step with full before/after state
        if self.recorder:
            self.recorder.record_vwap_step(
                step_type='live_update',
                strike=strike,
                option_type=option_type if option_type in ('CE', 'PE') else ('CE' if option_type == 'CALL' else 'PE'),
                expiry=expiry,
                candle_time=None,  # caller can set; live updates don't carry candle_time
                ohlc=ohlc_data,
                raw_volume=volume,
                is_interval_volume=is_interval,
                incremental_volume=incremental_volume,
                cum_tpv_before=cum_tpv_before,
                cum_volume_before=cum_vol_before,
                cum_tpv_after=self.vwap_running_totals[key]['tpv'],
                cum_volume_after=self.vwap_running_totals[key]['volume']
            )

        # Calculate VWAP
        if self.vwap_running_totals[key]['volume'] > 0:
            vwap = self.vwap_running_totals[key]['tpv'] / self.vwap_running_totals[key]['volume']
            return vwap
        else:
            return typical_price  # Fallback to typical price if no volume

    def _fetch_current_strike_candle(self, strike, option_type, expiry, current_time):
        """
        Fetch ONLY the latest 5-min candle for the current strike.

        Returns:
            dict: {
                'open': float,
                'high': float,
                'low': float,
                'close': float,
                'volume': int,
                'oi': int
            } or None if error
        """
        if not self.adapter:
            return None

        try:
            from datetime import timedelta

            # Convert CALL/PUT to CE/PE for adapter
            if option_type == 'CALL':
                option_type_code = 'CE'
            elif option_type == 'PUT':
                option_type_code = 'PE'
            else:
                option_type_code = option_type  # Already CE/PE

            # Calculate last complete 5-min boundary
            current_minute = current_time.minute
            boundary_minute = (current_minute // 5) * 5
            candle_start = current_time.replace(minute=boundary_minute, second=0, microsecond=0)
            from_time = candle_start - timedelta(minutes=5)
            # Subtract 1s so AngelOne formats to_time as "HH:MM-1" not "HH:MM",
            # preventing the just-started boundary candle from being returned.
            to_time = candle_start - timedelta(seconds=1)

            # Fetch candle for selected strike ONLY
            candles = self.adapter.get_historical_candles(
                underlying="NIFTY",
                option_type=option_type_code,
                strike=strike,
                expiry=expiry,
                from_time=from_time,
                to_time=to_time
            )

            if not candles:
                print(f"[{current_time}] ⚠️  No candle data for {option_type} {strike}")
                return None

            # Record all candles from this fetch to persistent store
            if self.recorder:
                self.recorder.record_candle_fetch(
                    fetch_reason='strategy_update',
                    strike=strike,
                    option_type=option_type_code,
                    expiry=expiry,
                    from_time=from_time,
                    to_time=to_time,
                    candles=candles
                )

            # Get last candle (most recent complete)
            last_candle = candles[-1]

            # Use OI from candle if available, otherwise fetch via quote API
            # (AngelOne candles never include OI, so quote API is always used)
            oi = last_candle.get('oi', 0)
            if oi == 0:
                oi = self._fetch_oi_for_strike(strike, option_type_code, expiry)

            return {
                'open': last_candle['open'],
                'high': last_candle['high'],
                'low': last_candle['low'],
                'close': last_candle['close'],
                'volume': last_candle['volume'],
                'oi': oi
            }

        except Exception as e:
            print(f"[{current_time}] ✗ Error fetching current candle: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _fetch_oi_for_strike(self, strike, option_type, expiry):
        """
        Fetch only OI using quote API (faster than candle).

        Args:
            option_type: Should be 'CE' or 'PE' (already converted from CALL/PUT)
        """
        try:
            quote = self.adapter.get_quote(
                underlying="NIFTY",
                option_type=option_type,
                strike=strike,
                expiry=expiry
            )
            if self.recorder and quote:
                self.recorder.record_quote(
                    fetch_reason='oi_fallback',
                    strike=strike,
                    option_type=option_type,
                    expiry=expiry,
                    quote=quote
                )
            return quote.oi if quote else 0
        except:
            return 0

    def get_status(self):
        """Get current strategy status"""
        positions = self.broker.get_open_positions()
        stats = self.broker.get_statistics()

        return {
            'current_date': self.current_date,
            'daily_direction': self.daily_direction,
            'daily_strike': self.daily_strike,
            'daily_expiry': self.daily_expiry,
            'daily_trade_taken': self.daily_trade_taken,
            'open_positions': len(positions),
            'statistics': stats
        }

    def get_instrument_token(self, strike: int, option_type: str, expiry: str = None) -> str:
        """
        Get instrument token for an option contract using the adapter.

        Uses ContractManager's token lookup for reliable instrument resolution
        instead of constructing broker-specific symbols.

        Args:
            strike: Strike price (e.g., 23000)
            option_type: 'CE', 'PE', 'CALL', or 'PUT'
            expiry: Expiry date (YYYY-MM-DD), defaults to daily_expiry

        Returns:
            str: Instrument token or empty string if not found
        """
        if expiry is None:
            expiry = self.daily_expiry

        if not expiry:
            return ""

        # Use contract_manager for token lookup
        if self.contract_manager:
            token = self.contract_manager.get_instrument_token(expiry, strike, option_type)
            if token:
                return token

        # Fallback: try adapter's resolution
        if self.adapter:
            contract = self.adapter._resolve_instrument("NIFTY", option_type, strike, expiry)
            if contract and contract.get('token'):
                return contract['token']

        return ""

    def get_option_contract(self, strike: int, option_type: str, expiry: str = None) -> dict:
        """
        Get full contract info (token + symbol) for an option.

        Args:
            strike: Strike price
            option_type: 'CE', 'PE', 'CALL', or 'PUT'
            expiry: Expiry date (YYYY-MM-DD), defaults to daily_expiry

        Returns:
            dict: {'token': '...', 'symbol': '...'} or empty dict
        """
        if expiry is None:
            expiry = self.daily_expiry

        if not expiry:
            return {}

        # Use contract_manager for contract lookup
        if self.contract_manager:
            contract = self.contract_manager.get_option_contract(expiry, strike, option_type)
            if contract:
                return contract

        # Fallback: try adapter's resolution
        if self.adapter:
            contract = self.adapter._resolve_instrument("NIFTY", option_type, strike, expiry)
            if contract:
                return contract

        return {}
