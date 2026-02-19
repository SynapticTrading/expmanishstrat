"""
Intraday Momentum OI Unwinding Strategy
Implements the trading logic based on Open Interest changes and VWAP
"""

import backtrader as bt
from datetime import datetime, time
import pandas as pd
import numpy as np
import signal
import sys
import csv
from pathlib import Path


class IntradayMomentumOI(bt.Strategy):
    """
    Strategy that trades based on:
    1. OI unwinding (short covering/long unwinding)
    2. Option price above VWAP
    3. Direction determined by max OI buildup
    """
    
    params = (
        # Entry parameters
        ('entry_start_time', time(9, 30)),
        ('entry_end_time', time(14, 30)),
        ('strikes_above_spot', 5),
        ('strikes_below_spot', 5),

        # Exit parameters
        ('exit_start_time', time(14, 50)),
        ('exit_end_time', time(15, 0)),
        ('initial_stop_loss_pct', 0.25),
        ('profit_threshold', 1.10),
        ('trailing_stop_pct', 0.10),
        ('vwap_stop_pct', 0.05),  # Exit if price is more than 5% below VWAP
        ('oi_increase_stop_pct', 0.10),  # Exit if OI increases more than 10% from entry

        # Position sizing
        ('position_size', 1),
        ('max_positions', 3),
        ('lot_size', 75),  # NIFTY lot size

        # Risk management
        ('avoid_monday_tuesday', False),

        # Options data and analyzer
        ('options_df', None),
        ('oi_analyzer', None),
    )
    
    def __init__(self):
        # Track positions
        self.positions_dict = {}  # key: order, value: position info
        self.current_position = None  # Current open position info
        self.pending_exit = False  # Flag to prevent repeated exit signals
        self.pending_entry = False  # Flag to prevent multiple entry orders

        # Store entry signal data for immediate execution (not next candle)
        self.pending_entry_price = None
        self.pending_entry_timestamp = None
        self.pending_entry_vwap = None
        self.pending_entry_oi = None
        self.pending_entry_oi_change = None

        # Track daily state
        self.current_date = None
        self.daily_direction = None  # 'CALL' or 'PUT'
        self.daily_strike = None
        self.daily_expiry = None
        self.daily_trade_taken = False  # Flag to restrict to 1 trade per day

        # Performance optimization: cache filtered options data for current day
        self.daily_options_cache = None
        self.cache_date = None

        # Incremental VWAP optimization: running totals per strike
        # Key: (strike, option_type, expiry), Value: {'tpv': float, 'volume': float, 'last_update': datetime}
        self.vwap_running_totals = {}
        self.vwap_cache_date = None

        # OI baseline per strike: set when strike is first established/updated
        # Key: (strike, option_type), Value: baseline OI
        self.entry_oi_baseline = {}

        # Performance tracking
        self.trade_log = []

        # Setup trade log file - write immediately to disk with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.trade_log_file = Path('reports') / f'trades_{timestamp}.csv'
        self.trade_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Write CSV header
        with open(self.trade_log_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'entry_time', 'exit_time', 'strike', 'option_type', 'expiry',
                'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct',
                'vwap_at_entry', 'vwap_at_exit', 'oi_at_entry', 'oi_change_at_entry', 'oi_at_exit'
            ])
            writer.writeheader()

        print(f"Trade log will be saved to: {self.trade_log_file}")

        # Setup signal handler for graceful shutdown
        def signal_handler(sig, frame):
            print('\n\n⚠️  Interrupt received! Saving summary...')
            self.save_summary_to_file()
            print('✓ Files saved. Exiting...')
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        print("Strategy initialized")
    
    def log(self, txt, dt=None):
        """Logging function"""
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'[{dt}] {txt}')
    
    def notify_order(self, order):
        """Handle order notifications - Using OPTION PRICES for P&L calculation"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            dt = self.datas[0].datetime.datetime(0)
            
            if order.isbuy():
                # Use saved entry price from signal time (for immediate execution)
                # This ensures entry happens at the price when conditions were met, not next candle
                option_type = 'CE' if self.daily_direction == 'CALL' else 'PE'

                if self.pending_entry_price is not None:
                    # Use saved data from signal time (for immediate execution, not next candle)
                    option_entry_price = self.pending_entry_price
                    vwap_at_entry = self.pending_entry_vwap
                    current_oi = self.pending_entry_oi
                    oi_change = self.pending_entry_oi_change

                    # Calculate OI change percentage for logging
                    oi_change_pct = (oi_change / current_oi) * 100 if current_oi and current_oi > 0 else 0

                    self.log(f'🔵 BUY OPTION EXECUTED: {option_type} {self.daily_strike} @ ₹{option_entry_price:.2f} '
                            f'(Expiry: {self.daily_expiry.date()}, 1 lot = {self.params.lot_size} qty)')

                    # Log entry data for verification
                    vwap_str = f'{vwap_at_entry:.2f}' if vwap_at_entry is not None else 'N/A'
                    oi_str = f'{current_oi:.0f}' if current_oi is not None else 'N/A'
                    oi_chg_str = f'{oi_change:.0f}' if oi_change is not None else 'N/A'
                    oi_pct_str = f'{oi_change_pct:.2f}%' if oi_change_pct is not None else 'N/A'
                    self.log(f'   📊 ENTRY DATA: VWAP={vwap_str}, OI={oi_str}, OI Change={oi_chg_str} ({oi_pct_str})')

                    # Reset pending flags and clear all saved entry data
                    self.pending_exit = False
                    self.pending_entry = False
                    self.pending_entry_price = None
                    self.pending_entry_timestamp = None
                    self.pending_entry_vwap = None
                    self.pending_entry_oi = None
                    self.pending_entry_oi_change = None

                    # Mark that we took a trade today (1 trade per day limit)
                    self.daily_trade_taken = True

                    # Store position info with OPTION details - use current_position for easy access
                    self.current_position = {
                        'entry_price': option_entry_price,  # OPTION price, not spot
                        'entry_time': dt,
                        'size': order.executed.size,
                        'strike': self.daily_strike,
                        'option_type': option_type,
                        'expiry': self.daily_expiry,
                        'stop_loss': option_entry_price * (1 - self.params.initial_stop_loss_pct),  # BELOW entry for longs
                        'trailing_stop': None,
                        'highest_price': option_entry_price,  # Track highest for longs
                        'vwap_at_entry': vwap_at_entry,
                        'oi_at_entry': current_oi,
                        'oi_change_at_entry': oi_change,
                    }
                    self.positions_dict[order.ref] = self.current_position
                else:
                    self.log(f'⚠️  ERROR: No saved entry price found!')
                    
            else:
                # Get actual option price at exit
                # Use current_position since SELL order has different ref than BUY order!
                if self.current_position is not None:
                    pos_info = self.current_position

                    option_data = self.params.oi_analyzer.get_option_price_data(
                        strike=pos_info['strike'],
                        option_type=pos_info['option_type'],
                        timestamp=pd.Timestamp(dt),
                        expiry_date=pos_info['expiry']
                    )

                    if option_data is not None:
                        # Use theoretical exit price if stop was triggered, else use actual execution price
                        if 'stop_loss_triggered_price' in pos_info:
                            # Cap at stop loss price (strict 25% stop)
                            option_exit_price = pos_info['stop_loss']
                        elif 'trailing_stop_triggered_price' in pos_info:
                            # Use trailing stop price
                            option_exit_price = pos_info['trailing_stop']
                        elif 'vwap_stop_triggered_price' in pos_info:
                            # Use actual price when VWAP stop was triggered
                            option_exit_price = pos_info['vwap_stop_triggered_price']
                        elif 'oi_stop_triggered_price' in pos_info:
                            # Use actual price when OI stop was triggered
                            option_exit_price = pos_info['oi_stop_triggered_price']
                        else:
                            option_exit_price = option_data['close']

                        # Calculate VWAP at exit (from running totals — same as paper/live trading)
                        vwap_at_exit = self._get_vwap_from_totals(
                            strike=pos_info['strike'],
                            option_type=pos_info['option_type'],
                            expiry=pos_info['expiry']
                        )

                        # Get OI at exit
                        current_oi_exit, _, _ = self.params.oi_analyzer.calculate_oi_change(
                            strike=pos_info['strike'],
                            option_type=pos_info['option_type'],
                            timestamp=pd.Timestamp(dt),
                            expiry_date=pos_info['expiry']
                        )

                        # Calculate P&L based on OPTION prices
                        # For long positions: profit when price goes up, loss when price goes down
                        # Multiply by lot_size for REALISTIC P&L (what you'd actually make/lose in real trading)
                        pnl = (option_exit_price - pos_info['entry_price']) * abs(order.executed.size) * self.params.lot_size
                        pnl_pct = ((option_exit_price - pos_info['entry_price']) / pos_info['entry_price']) * 100

                        self.log(f'🔴 SELL OPTION EXECUTED: {pos_info["option_type"]} {pos_info["strike"]} @ ₹{option_exit_price:.2f} '
                                f'| Entry: ₹{pos_info["entry_price"]:.2f} | P&L: ₹{pnl:.2f} ({pnl_pct:+.2f}%)')

                        # Log exit data for verification
                        vwap_exit_str = f'{vwap_at_exit:.2f}' if vwap_at_exit is not None else 'N/A'
                        oi_exit_str = f'{current_oi_exit:.0f}' if current_oi_exit is not None else 'N/A'
                        self.log(f'   📊 EXIT DATA: VWAP={vwap_exit_str}, OI={oi_exit_str}')

                        trade_record = {
                            'entry_time': pos_info['entry_time'],
                            'exit_time': dt,
                            'strike': pos_info['strike'],
                            'option_type': pos_info['option_type'],
                            'expiry': pos_info['expiry'],
                            'entry_price': pos_info['entry_price'],
                            'exit_price': option_exit_price,
                            'size': order.executed.size,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'vwap_at_entry': pos_info.get('vwap_at_entry'),
                            'vwap_at_exit': vwap_at_exit,
                            'oi_at_entry': pos_info.get('oi_at_entry'),
                            'oi_change_at_entry': pos_info.get('oi_change_at_entry'),
                            'oi_at_exit': current_oi_exit,
                        }
                        self.trade_log.append(trade_record)

                        # ✅ WRITE TRADE TO CSV IMMEDIATELY - NO DATA LOSS!
                        with open(self.trade_log_file, 'a', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=[
                                'entry_time', 'exit_time', 'strike', 'option_type', 'expiry',
                                'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct',
                                'vwap_at_entry', 'vwap_at_exit', 'oi_at_entry', 'oi_change_at_entry', 'oi_at_exit'
                            ])
                            writer.writerow(trade_record)

                        # Clear current position
                        self.current_position = None
                        self.pending_exit = False  # Reset pending exit flag
                    else:
                        self.log(f'⚠️  ERROR: Could not get option price at exit!')
                        self.pending_exit = False  # Reset even on error
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected')
    
    def notify_trade(self, trade):
        """Handle trade notifications"""
        if not trade.isclosed:
            return

        # NOTE: trade.pnl is based on SPOT prices (data feed), NOT option prices
        # We calculate actual option P&L in notify_order() and log it there
        # This notify_trade callback is kept for compatibility but not used for logging
        pass
    
    def should_skip_day(self, dt):
        """Check if we should skip trading on this day"""
        if self.params.avoid_monday_tuesday:
            weekday = dt.weekday()
            if weekday in [0, 1]:  # Monday = 0, Tuesday = 1
                return True
        return False
    
    def is_trading_time(self, dt):
        """Check if current time is within entry window"""
        current_time = dt.time()
        return self.params.entry_start_time <= current_time <= self.params.entry_end_time
    
    def is_exit_time(self, dt):
        """Check if it's time to exit positions"""
        current_time = dt.time()
        return current_time >= self.params.exit_start_time
    
    def get_spot_price(self):
        """Get current spot price from data feed"""
        return self.datas[0].close[0]

    def calculate_vwap_for_option(self, strike, option_type, timestamp, expiry_date):
        """
        Calculate VWAP for a specific option at a given timestamp.
        Full recalculation from cache — kept for reference only.
        Use _get_vwap_from_totals() for all entry/exit decisions.
        Returns VWAP value or None if insufficient data.
        """
        dt_ts = pd.Timestamp(timestamp)
        current_trade_date = dt_ts.date()

        # Check if we have cached data for today
        if self.daily_options_cache is None or self.cache_date != current_trade_date:
            return None

        # Get all history from market open to current time for this strike
        mask = (
            (self.daily_options_cache['strike'] == strike) &
            (self.daily_options_cache['option_type'] == option_type) &
            (self.daily_options_cache['datetime'] <= dt_ts)
        )
        option_history = self.daily_options_cache[mask].copy()

        if len(option_history) < 2:
            return None

        # Calculate VWAP using OHLC/4 formula
        option_history['typical_price'] = (
            option_history['open'] + option_history['high'] + option_history['low'] + option_history['close']
        ) / 4.0
        option_history['volume_filled'] = option_history['volume'].replace(0, 1)

        total_tpv = (option_history['typical_price'] * option_history['volume_filled']).sum()
        total_volume = option_history['volume_filled'].sum()

        vwap = total_tpv / total_volume if total_volume > 0 else None
        return vwap

    def _get_vwap_from_totals(self, strike, option_type, expiry):
        """
        Return current VWAP from running totals — same approach as paper/live trading.
        Uses the same incremental TPV/volume accumulators built during check_entry_conditions().
        Returns None if running totals not yet initialized for this strike.
        """
        key = (strike, option_type, expiry)
        running = self.vwap_running_totals.get(key)
        if running and running.get('volume', 0) > 0:
            return running['tpv'] / running['volume']
        return None
    
    def analyze_market(self, dt):
        """
        Analyze market to determine direction and strike
        Called once per day
        """
        if self.params.options_df is None or self.params.oi_analyzer is None:
            self.log('ERROR: Options data or OI analyzer not available')
            return False
        
        spot_price = self.get_spot_price()
        self.log(f'Starting daily analysis - Spot: {spot_price:.2f}')
        
        # Get closest expiry
        expiry = self.params.oi_analyzer.get_closest_expiry(pd.Timestamp(dt))
        if expiry is None:
            self.log('ERROR: No expiry found')
            return False
        
        self.log(f'Found expiry: {expiry.date()}')
        
        self.daily_expiry = expiry
        
        # Get strikes near spot
        options_near_spot, selected_strikes = self.params.oi_analyzer.get_strikes_near_spot(
            spot_price=spot_price,
            timestamp=pd.Timestamp(dt),
            expiry_date=expiry,
            num_strikes_above=self.params.strikes_above_spot,
            num_strikes_below=self.params.strikes_below_spot
        )
        
        if options_near_spot is None or len(options_near_spot) == 0:
            self.log(f'ERROR: No options data found near spot at {pd.Timestamp(dt)}')
            return False
        
        self.log(f'Found {len(options_near_spot)} options near spot, {len(selected_strikes)} strikes')
        
        # Calculate max OI buildup
        max_call_strike, max_put_strike, call_distance, put_distance = \
            self.params.oi_analyzer.calculate_max_oi_buildup(options_near_spot, spot_price)
        
        if max_call_strike is None or max_put_strike is None:
            self.log('ERROR: Could not determine max OI buildup')
            return False
        
        self.log(f'Max Call OI: {max_call_strike}, Max Put OI: {max_put_strike}')
        
        # Determine direction
        self.daily_direction = self.params.oi_analyzer.determine_direction(call_distance, put_distance)
        
        if self.daily_direction is None:
            self.log('ERROR: Could not determine direction')
            return False
        
        self.log(f'Direction determined: {self.daily_direction} (Call dist: {call_distance:.2f}, Put dist: {put_distance:.2f})')
        
        # Get nearest strike based on direction
        option_type = 'CE' if self.daily_direction == 'CALL' else 'PE'
        self.daily_strike = self.params.oi_analyzer.get_nearest_strike(
            spot_price, self.daily_direction, selected_strikes
        )
        
        if self.daily_strike is None:
            self.log(f'ERROR: Could not find suitable strike for {self.daily_direction}')
            return False
        
        self.log(f'✓ Daily Analysis Complete: Direction={self.daily_direction}, Strike={self.daily_strike}, '
                f'Expiry={self.daily_expiry.date()}, Spot={spot_price:.2f}')
        
        return True
    
    def check_entry_conditions(self, dt):
        """
        Check if entry conditions are met
        Returns option price if conditions met, None otherwise

        PDF Strategy: "Keep on Updating CallStrike/PutStrike till entry is found"
        This means the strike should be dynamically updated based on current spot price
        """
        if self.daily_direction is None or self.daily_expiry is None:
            # Only log once per minute to avoid spam
            if dt.minute % 10 == 0:
                self.log(f'No daily analysis available yet (Dir={self.daily_direction}, Expiry={self.daily_expiry})')
            return None

        # Check if we already took a trade today (1 trade per day limit)
        if self.daily_trade_taken:
            return None

        # Check if we have room for more positions (using Backtrader's built-in position tracking)
        has_position = self.position.size != 0
        if has_position or self.pending_entry:
            # Skip verbose logging - just return
            return None

        # ✅ DYNAMIC STRIKE UPDATE - As per PDF: "Keep on Updating CallStrike/PutStrike till entry is found"
        # Get current spot price
        spot_price = self.get_spot_price()

        # Get strikes near current spot
        options_near_spot, selected_strikes = self.params.oi_analyzer.get_strikes_near_spot(
            spot_price=spot_price,
            timestamp=pd.Timestamp(dt),
            expiry_date=self.daily_expiry,
            num_strikes_above=self.params.strikes_above_spot,
            num_strikes_below=self.params.strikes_below_spot
        )

        if options_near_spot is None or len(selected_strikes) == 0:
            return None

        # Update strike to nearest based on current spot and direction
        updated_strike = self.params.oi_analyzer.get_nearest_strike(
            spot_price, self.daily_direction, selected_strikes
        )

        if updated_strike is None:
            return None

        # Log strike updates (only when it changes)
        if updated_strike != self.daily_strike:
            self.log(f'📍 STRIKE UPDATED: {self.daily_strike} → {updated_strike} (Spot: {spot_price:.2f})')
            # Reset OI baseline for the old strike so new strike gets a fresh baseline
            old_option_type = 'CE' if self.daily_direction == 'CALL' else 'PE'
            self.entry_oi_baseline.pop((self.daily_strike, old_option_type), None)
            self.daily_strike = updated_strike

        option_type = 'CE' if self.daily_direction == 'CALL' else 'PE'

        # Log what we're looking for (every 30 min)
        if dt.minute % 30 == 0:
            expiry_str = self.daily_expiry.date() if self.daily_expiry else 'None'
            self.log(f'Checking entry: {option_type} {self.daily_strike}, Expiry={expiry_str}')

        # Get current OI (use oi_analyzer only to fetch the value, ignore its bar-to-bar change)
        current_oi, _, _ = self.params.oi_analyzer.calculate_oi_change(
            strike=self.daily_strike,
            option_type=option_type,
            timestamp=pd.Timestamp(dt),
            expiry_date=self.daily_expiry
        )

        if current_oi is None:
            if dt.minute % 30 == 0:
                self.log(f'⚠️  No OI data found for {option_type} {self.daily_strike} at {pd.Timestamp(dt)}')
            return None

        # OI change vs baseline (set when strike is first established/updated)
        baseline_key = (self.daily_strike, option_type)
        if baseline_key not in self.entry_oi_baseline:
            # First candle for this strike - record as baseline, no signal yet
            self.entry_oi_baseline[baseline_key] = current_oi
            oi_change = 0
            oi_change_pct = 0.0
        else:
            baseline_oi = self.entry_oi_baseline[baseline_key]
            oi_change = current_oi - baseline_oi
            oi_change_pct = (oi_change / baseline_oi * 100) if baseline_oi > 0 else 0.0

        # Check if OI is unwinding (below baseline)
        is_unwinding = oi_change < 0

        # Log OI status every 30 minutes
        if dt.minute % 30 == 0:
            status = "UNWINDING ✓" if is_unwinding else "BUILDING"
            self.log(f'{option_type} {self.daily_strike}: OI={current_oi:.0f}, Change={oi_change:.0f} ({oi_change_pct:.2f}%) - {status}')
        
        if not is_unwinding:
            return None
        
        # Get option price data
        option_data = self.params.oi_analyzer.get_option_price_data(
            strike=self.daily_strike,
            option_type=option_type,
            timestamp=pd.Timestamp(dt),
            expiry_date=self.daily_expiry
        )
        
        if option_data is None:
            if dt.minute % 30 == 0:
                self.log(f'⚠️  No option price data for {option_type} {self.daily_strike}')
            return None
        
        option_price = option_data['close']

        # ===== INCREMENTAL VWAP CALCULATION =====
        # VWAP = Sum(Typical Price * Volume) / Sum(Volume) from market open (9:15 AM) to current time
        # Instead of recalculating from scratch every minute, maintain running totals

        dt_ts = pd.Timestamp(dt)
        current_trade_date = dt_ts.date()

        # Reset running totals at start of new trading day
        if self.vwap_cache_date != current_trade_date:
            self.vwap_running_totals = {}  # Clear all running totals
            self.vwap_cache_date = current_trade_date
            self.log(f"🔄 Reset VWAP running totals for new day: {current_trade_date}")

        # Create key for this specific option
        vwap_key = (self.daily_strike, option_type, self.daily_expiry)

        # Check if we need to update running totals for this option
        if vwap_key not in self.vwap_running_totals:
            # Initialize running totals - fetch ALL data from market open till now
            # Cache should already exist from analyze_market(), but check to be safe
            if self.daily_options_cache is None or self.cache_date != current_trade_date:
                self.log(f"⚠️  WARNING: Daily cache not found, this should not happen!")
                return None

            # Get all history from market open to current time for this strike
            mask = (
                (self.daily_options_cache['strike'] == self.daily_strike) &
                (self.daily_options_cache['option_type'] == option_type) &
                (self.daily_options_cache['datetime'] <= dt_ts)
            )
            option_history = self.daily_options_cache[mask].copy()

            if len(option_history) < 2:
                if dt.minute % 30 == 0:
                    self.log(f'⚠️  Insufficient history for VWAP: only {len(option_history)} records for {option_type} {self.daily_strike}')
                return None

            # Calculate initial running totals from all available history (OHLC/4)
            option_history['typical_price'] = (
                option_history['open'] + option_history['high'] + option_history['low'] + option_history['close']
            ) / 4.0
            option_history['volume_filled'] = option_history['volume'].replace(0, 1)

            total_tpv = (option_history['typical_price'] * option_history['volume_filled']).sum()
            total_volume = option_history['volume_filled'].sum()

            # Store running totals
            self.vwap_running_totals[vwap_key] = {
                'tpv': total_tpv,
                'volume': total_volume,
                'last_update': dt_ts
            }

            # Log initialization (only once per strike per day)
            self.log(f"🎯 Initialized VWAP for {option_type} {self.daily_strike}: {len(option_history)} bars from 9:15 AM")

        else:
            # Incremental update: add only new bar(s) since last update
            last_update = self.vwap_running_totals[vwap_key]['last_update']

            # Check if there's a new bar to add (current time > last update)
            if dt_ts > last_update:
                # Get only the new bar(s) since last update
                mask = (
                    (self.daily_options_cache['strike'] == self.daily_strike) &
                    (self.daily_options_cache['option_type'] == option_type) &
                    (self.daily_options_cache['datetime'] > last_update) &
                    (self.daily_options_cache['datetime'] <= dt_ts)
                )
                new_bars = self.daily_options_cache[mask].copy()

                if len(new_bars) > 0:
                    # Calculate contribution from new bar(s) only (OHLC/4)
                    new_bars['typical_price'] = (
                        new_bars['open'] + new_bars['high'] + new_bars['low'] + new_bars['close']
                    ) / 4.0
                    new_bars['volume_filled'] = new_bars['volume'].replace(0, 1)

                    new_tpv = (new_bars['typical_price'] * new_bars['volume_filled']).sum()
                    new_volume = new_bars['volume_filled'].sum()

                    # Update running totals (INCREMENTAL - just add new contribution)
                    self.vwap_running_totals[vwap_key]['tpv'] += new_tpv
                    self.vwap_running_totals[vwap_key]['volume'] += new_volume
                    self.vwap_running_totals[vwap_key]['last_update'] = dt_ts

        # Calculate VWAP from running totals (O(1) operation)
        running_totals = self.vwap_running_totals[vwap_key]
        vwap = running_totals['tpv'] / running_totals['volume'] if running_totals['volume'] > 0 else option_price
        
        # Log VWAP check every 30 minutes
        if dt.minute % 30 == 0:
            price_vs_vwap = "ABOVE ✓" if option_price > vwap else "BELOW ✗"
            self.log(f'{option_type} {self.daily_strike}: Price={option_price:.2f}, VWAP={vwap:.2f} - {price_vs_vwap}')
        
        # Check if option price is above VWAP
        if option_price > vwap:
            self.log(f'🎯 ENTRY SIGNAL: {option_type} {self.daily_strike} - Price: {option_price:.2f}, '
                    f'VWAP: {vwap:.2f}, OI Change: {oi_change:.0f} ({oi_change_pct:.2f}%)')

            # Save all signal data for immediate execution (not next candle)
            self.pending_entry_price = option_price
            self.pending_entry_timestamp = dt
            self.pending_entry_vwap = vwap
            self.pending_entry_oi = current_oi
            self.pending_entry_oi_change = oi_change

            return option_price

        return None
    
    def _update_vwap_for_position(self, dt, pos_info):
        """
        Incrementally update VWAP running totals for the open position.
        Called every 5-min candle while in position — mirrors paper trading's
        _update_vwap_for_positions() so VWAP stays current post-entry.
        """
        vwap_key = (pos_info['strike'], pos_info['option_type'], pos_info['expiry'])

        if vwap_key not in self.vwap_running_totals:
            return  # Not yet initialized — nothing to update

        if self.daily_options_cache is None:
            return

        dt_ts = pd.Timestamp(dt)
        last_update = self.vwap_running_totals[vwap_key]['last_update']

        if dt_ts <= last_update:
            return  # No new bar yet

        # Fetch only new bars since last update (same logic as check_entry_conditions)
        mask = (
            (self.daily_options_cache['strike'] == pos_info['strike']) &
            (self.daily_options_cache['option_type'] == pos_info['option_type']) &
            (self.daily_options_cache['datetime'] > last_update) &
            (self.daily_options_cache['datetime'] <= dt_ts)
        )
        new_bars = self.daily_options_cache[mask].copy()

        if len(new_bars) == 0:
            return

        new_bars['typical_price'] = (
            new_bars['open'] + new_bars['high'] + new_bars['low'] + new_bars['close']
        ) / 4.0
        new_bars['volume_filled'] = new_bars['volume'].replace(0, 1)

        new_tpv = (new_bars['typical_price'] * new_bars['volume_filled']).sum()
        new_volume = new_bars['volume_filled'].sum()

        self.vwap_running_totals[vwap_key]['tpv'] += new_tpv
        self.vwap_running_totals[vwap_key]['volume'] += new_volume
        self.vwap_running_totals[vwap_key]['last_update'] = dt_ts

    def manage_positions(self, dt):
        """Manage open positions - update stops and check exits using OPTION PRICES"""
        # Don't check exits if we already have a pending exit order
        if self.pending_exit or self.current_position is None:
            return

        pos_info = self.current_position

        # Update VWAP running totals with any new bars since last update
        # Mirrors paper trading's _update_vwap_for_positions() so VWAP is current
        self._update_vwap_for_position(dt, pos_info)

        # Get current OPTION price
        option_data = self.params.oi_analyzer.get_option_price_data(
            strike=pos_info['strike'],
            option_type=pos_info['option_type'],
            timestamp=pd.Timestamp(dt),
            expiry_date=pos_info['expiry']
        )

        if option_data is None:
            return  # Skip if we can't get current option price

        current_price = option_data['close']
        entry_price = pos_info['entry_price']

        # ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
        if current_price <= pos_info['stop_loss']:
            # ✅ STRICT EXECUTION: Exit at EXACTLY the 25% stop loss price
            strict_exit_price = pos_info['stop_loss']
            strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

            self.log(f'🛑 STOP LOSS HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, STRICT Exit: ₹{strict_exit_price:.2f} (exactly -25.0% SL), '
                    f'STRICT P&L: {strict_pnl_pct:.1f}%')

            # Store strict exit price for accurate P&L calculation
            pos_info['stop_loss_triggered_price'] = strict_exit_price
            self.close()
            self.pending_exit = True  # Mark that we have a pending exit
            return  # Exit immediately, don't process more positions

        # Calculate current P&L to check if we're in a losing position
        pnl = current_price - entry_price
        is_losing = pnl < 0

        # Check VWAP-based stop (ONLY when PnL is negative - trade is in a loss)
        if is_losing:
            current_vwap = self._get_vwap_from_totals(
                strike=pos_info['strike'],
                option_type=pos_info['option_type'],
                expiry=pos_info['expiry']
            )

            if current_vwap is not None:
                vwap_threshold = current_vwap * (1 - self.params.vwap_stop_pct)
                if current_price < vwap_threshold:
                    vwap_diff_pct = ((current_price - current_vwap) / current_vwap) * 100
                    strict_pnl_pct = ((vwap_threshold - entry_price) / entry_price) * 100
                    self.log(f'📊 VWAP STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Current: ₹{current_price:.2f} ({vwap_diff_pct:.1f}% below VWAP), '
                            f'STRICT Exit: ₹{vwap_threshold:.2f} (exactly -{self.params.vwap_stop_pct*100:.1f}% below VWAP ₹{current_vwap:.2f}), '
                            f'STRICT P&L: {strict_pnl_pct:.1f}%')
                    # Use exact threshold price (not worse current_price) — consistent with SL and trailing stop
                    pos_info['vwap_stop_triggered_price'] = vwap_threshold
                    self.close()
                    self.pending_exit = True
                    return

        # Check OI-based stop (ONLY when PnL is negative - trade is in a loss)
        if is_losing:
            current_oi, oi_change, oi_change_pct = self.params.oi_analyzer.calculate_oi_change(
                strike=pos_info['strike'],
                option_type=pos_info['option_type'],
                timestamp=pd.Timestamp(dt),
                expiry_date=pos_info['expiry']
            )

            if current_oi is not None and pos_info.get('oi_at_entry') is not None:
                oi_increase_pct = ((current_oi - pos_info['oi_at_entry']) / pos_info['oi_at_entry']) * 100
                if oi_increase_pct > (self.params.oi_increase_stop_pct * 100):
                    strict_pnl_pct = (pnl / entry_price) * 100
                    self.log(f'📈 OI INCREASE STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Entry OI: {pos_info["oi_at_entry"]:.0f}, Current OI: {current_oi:.0f} (+{oi_increase_pct:.1f}%), '
                            f'Current Price: ₹{current_price:.2f} (P&L: {strict_pnl_pct:.1f}%)')
                    # Use current_price at trigger — best approximation for OI stop (no exact price level to interpolate to)
                    pos_info['oi_stop_triggered_price'] = current_price
                    self.close()
                    self.pending_exit = True
                    return

        # Update highest price (for long positions, profit increases as price increases)
        if current_price > pos_info['highest_price']:
            pos_info['highest_price'] = current_price

        # Calculate current profit percentage
        profit_pct = (current_price - entry_price) / entry_price

        # Activate trailing stop if profit threshold reached AND not already active
        if pos_info['trailing_stop'] is None and profit_pct >= (self.params.profit_threshold - 1):
            # Activate trailing stop (for longs: lock in profit as price goes up)
            trailing_stop = pos_info['highest_price'] * (1 - self.params.trailing_stop_pct)
            pos_info['trailing_stop'] = trailing_stop
            self.log(f'✅ TRAILING STOP ACTIVATED: {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Stop: ₹{trailing_stop:.2f}, Highest: ₹{pos_info["highest_price"]:.2f}')

        # If trailing stop is active, update it based on new highest price
        if pos_info['trailing_stop'] is not None:
            # Update trailing stop to new highest price (moves up only, never down)
            new_trailing_stop = pos_info['highest_price'] * (1 - self.params.trailing_stop_pct)
            if new_trailing_stop > pos_info['trailing_stop']:
                old_stop = pos_info['trailing_stop']
                pos_info['trailing_stop'] = new_trailing_stop
                self.log(f'⬆️  TRAILING STOP UPDATED: ₹{old_stop:.2f} → ₹{new_trailing_stop:.2f}')

            # Check if trailing stop was hit (independently of profit percentage)
            if current_price <= pos_info['trailing_stop']:
                # ✅ STRICT EXECUTION: Exit at EXACTLY the trailing stop price (10% below peak)
                strict_exit_price = pos_info['trailing_stop']
                strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

                self.log(f'📉 TRAILING STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{pos_info["trailing_stop"]:.2f}, '
                        f'Peak: ₹{pos_info["highest_price"]:.2f}, '
                        f'STRICT Exit: ₹{strict_exit_price:.2f} (exactly -10.0% from peak), '
                        f'STRICT P&L: {strict_pnl_pct:.1f}%')

                # Store strict exit price for accurate P&L calculation
                pos_info['trailing_stop_triggered_price'] = strict_exit_price
                self.close()
                self.pending_exit = True  # Mark that we have a pending exit
                return  # Exit immediately, don't process more positions
    
    def next(self):
        """Main strategy logic called on each bar"""
        dt = self.datas[0].datetime.datetime(0)
        current_date = dt.date()

        # Check if new day
        if self.current_date is None or current_date != self.current_date:
            self.current_date = current_date
            self.daily_direction = None
            self.daily_strike = None
            self.daily_expiry = None
            self.pending_exit = False  # Reset pending exit for new day
            self.pending_entry = False  # Reset pending entry for new day
            self.daily_trade_taken = False  # Reset trade counter for new day

            # Clear any pending entry signal data from previous day
            self.pending_entry_price = None
            self.pending_entry_timestamp = None
            self.pending_entry_vwap = None
            self.pending_entry_oi = None
            self.pending_entry_oi_change = None

            # Reset OI baseline for new day
            self.entry_oi_baseline = {}

            # CRITICAL: Clear OI analyzer cache BEFORE analyze_market()
            # analyze_market() needs to query full dataset to find new expiry
            # After that, we'll cache data for the new expiry
            if self.params.oi_analyzer is not None:
                self.params.oi_analyzer.clear_working_data()
                self.log(f'🔄 Cleared OI analyzer cache for new day: {current_date}')

            # Check if we should skip this day
            if self.should_skip_day(dt):
                self.log(f'Skipping day: {current_date}')
                return

            # Analyze market for the day (uses full dataset to find expiry)
            analysis_success = self.analyze_market(dt)

            # After successful analysis, cache today's data for the determined expiry
            if analysis_success and self.daily_expiry is not None:
                dt_ts = pd.Timestamp(dt)
                market_open_today = pd.Timestamp(dt_ts.date()) + pd.Timedelta(hours=9, minutes=15)
                market_close_today = pd.Timestamp(dt_ts.date()) + pd.Timedelta(hours=15, minutes=30)

                # Create cache for today's data with the newly determined expiry
                cache_mask = (
                    (self.params.options_df['expiry'] == self.daily_expiry) &
                    (self.params.options_df['datetime'] >= market_open_today) &
                    (self.params.options_df['datetime'] <= market_close_today)
                )
                self.daily_options_cache = self.params.options_df[cache_mask].copy()
                self.cache_date = current_date
                self.log(f"📦 Cached {len(self.daily_options_cache)} options records for {current_date} with expiry {self.daily_expiry.date()}")

                # Set the cached data in OI analyzer
                if self.params.oi_analyzer is not None:
                    self.params.oi_analyzer.set_working_data(self.daily_options_cache)
                    self.log(f"⚡ OI Analyzer now using cached data ({len(self.daily_options_cache)} rows instead of {len(self.params.options_df)})")
        
        # Force exit all positions near market close
        if self.is_exit_time(dt):
            if self.current_position is not None and not self.pending_exit:
                self.log(f'END OF DAY - Closing all positions')
                self.close()
                self.pending_exit = True
            return
        
        # Manage existing positions (check using our manual position tracking)
        if self.current_position is not None and not self.pending_exit:
            self.manage_positions(dt)
        
        # Check for new entries
        if self.is_trading_time(dt):
            entry_price = self.check_entry_conditions(dt)
            if entry_price is not None:
                # Place buy order - 1 unit in Backtrader represents 1 lot (75 qty) in real trading
                # Note: check_entry_conditions() already saved all signal data for immediate execution
                self.log(f'📈 PLACING BUY ORDER: size={self.params.position_size}, expected_price={entry_price:.2f}')
                self.buy(size=self.params.position_size)
                self.pending_entry = True  # Mark that we have a pending entry order
    
    def save_summary_to_file(self):
        """Save trade summary to files - called on ANY exit"""
        import json

        summary_file = Path('reports') / 'trade_summary.txt'
        summary_json = Path('reports') / 'trade_summary.json'

        summary_data = {
            'final_portfolio_value': float(self.broker.getvalue()),
            'total_trades': len(self.trade_log),
        }

        if len(self.trade_log) > 0:
            df_trades = pd.DataFrame(self.trade_log)
            summary_data.update({
                'winning_trades': int(len(df_trades[df_trades['pnl'] > 0])),
                'losing_trades': int(len(df_trades[df_trades['pnl'] < 0])),
                'win_rate': float(len(df_trades[df_trades['pnl'] > 0]) / len(df_trades) * 100),
                'total_pnl': float(df_trades['pnl'].sum()),
                'average_pnl': float(df_trades['pnl'].mean()),
                'average_pnl_pct': float(df_trades['pnl_pct'].mean()),
                'best_trade': float(df_trades['pnl'].max()),
                'worst_trade': float(df_trades['pnl'].min())
            })

        # Write text summary
        with open(summary_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("TRADE SUMMARY\n")
            f.write("="*80 + "\n")
            f.write(f"Final Portfolio Value: ₹{summary_data['final_portfolio_value']:,.2f}\n")
            f.write(f"Total Trades: {summary_data['total_trades']}\n")

            if len(self.trade_log) > 0:
                f.write(f"Winning Trades: {summary_data['winning_trades']}\n")
                f.write(f"Losing Trades: {summary_data['losing_trades']}\n")
                f.write(f"Win Rate: {summary_data['win_rate']:.2f}%\n")
                f.write(f"Total PnL: ₹{summary_data['total_pnl']:,.2f}\n")
                f.write(f"Average PnL: ₹{summary_data['average_pnl']:,.2f}\n")
                f.write(f"Average PnL %: {summary_data['average_pnl_pct']:.2f}%\n")
                f.write(f"Best Trade: ₹{summary_data['best_trade']:,.2f}\n")
                f.write(f"Worst Trade: ₹{summary_data['worst_trade']:,.2f}\n")
            f.write("="*80 + "\n")

        # Write JSON summary
        with open(summary_json, 'w') as f:
            json.dump(summary_data, f, indent=2, default=str)

        print(f"\n✓ Summary saved to: {summary_file}")
        print(f"✓ Summary JSON saved to: {summary_json}")

    def stop(self):
        """Called when strategy ends"""
        self.log(f'Strategy Ended. Final Portfolio Value: {self.broker.getvalue():.2f}')

        # Save summary to file IMMEDIATELY
        self.save_summary_to_file()

        # Print trade summary to console
        if len(self.trade_log) > 0:
            df_trades = pd.DataFrame(self.trade_log)
            print("\n" + "="*80)
            print("TRADE SUMMARY")
            print("="*80)
            print(f"Total Trades: {len(df_trades)}")
            print(f"Winning Trades: {len(df_trades[df_trades['pnl'] > 0])}")
            print(f"Losing Trades: {len(df_trades[df_trades['pnl'] < 0])}")
            print(f"Win Rate: {len(df_trades[df_trades['pnl'] > 0]) / len(df_trades) * 100:.2f}%")
            print(f"Total PnL: {df_trades['pnl'].sum():.2f}")
            print(f"Average PnL: {df_trades['pnl'].mean():.2f}")
            print(f"Average PnL%: {df_trades['pnl_pct'].mean():.2f}%")
            print("="*80)
        else:
            print("\nNo trades were recorded")
