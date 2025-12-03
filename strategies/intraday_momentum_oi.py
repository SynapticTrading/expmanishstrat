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
        
        # Position sizing
        ('position_size', 1),
        ('max_positions', 3),
        
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

        # Track daily state
        self.current_date = None
        self.daily_direction = None  # 'CALL' or 'PUT'
        self.daily_strike = None
        self.daily_expiry = None

        # Performance optimization: cache filtered options data for current day
        self.daily_options_cache = None
        self.cache_date = None

        # Incremental VWAP optimization: running totals per strike
        # Key: (strike, option_type, expiry), Value: {'tpv': float, 'volume': float, 'last_update': datetime}
        self.vwap_running_totals = {}
        self.vwap_cache_date = None

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
                'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct'
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
                # Get actual option price at entry
                option_type = 'CE' if self.daily_direction == 'CALL' else 'PE'
                option_data = self.params.oi_analyzer.get_option_price_data(
                    strike=self.daily_strike,
                    option_type=option_type,
                    timestamp=pd.Timestamp(dt),
                    expiry_date=self.daily_expiry
                )
                
                if option_data is not None:
                    option_entry_price = option_data['close']
                    
                    self.log(f'🔵 BUY OPTION EXECUTED: {option_type} {self.daily_strike} @ ₹{option_entry_price:.2f} '
                            f'(Expiry: {self.daily_expiry.date()}, Lot size: {order.executed.size})')

                    # Reset pending flags
                    self.pending_exit = False
                    self.pending_entry = False

                    # Store position info with OPTION details - use current_position for easy access
                    self.current_position = {
                        'entry_price': option_entry_price,  # OPTION price, not spot
                        'entry_time': dt,
                        'size': order.executed.size,
                        'strike': self.daily_strike,
                        'option_type': option_type,
                        'expiry': self.daily_expiry,
                        'stop_loss': option_entry_price * (1 + self.params.initial_stop_loss_pct),  # ABOVE entry for shorts
                        'trailing_stop': None,
                        'lowest_price': option_entry_price,  # Track lowest for shorts
                    }
                    self.positions_dict[order.ref] = self.current_position
                else:
                    self.log(f'⚠️  ERROR: Could not get option price at entry!')
                    
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
                        else:
                            option_exit_price = option_data['close']

                        # Calculate P&L based on OPTION prices
                        # For short positions: profit when price goes down, loss when price goes up
                        pnl = (pos_info['entry_price'] - option_exit_price) * abs(order.executed.size)
                        pnl_pct = ((pos_info['entry_price'] - option_exit_price) / pos_info['entry_price']) * 100
                        
                        self.log(f'🔴 SELL OPTION EXECUTED: {pos_info["option_type"]} {pos_info["strike"]} @ ₹{option_exit_price:.2f} '
                                f'| Entry: ₹{pos_info["entry_price"]:.2f} | P&L: ₹{pnl:.2f} ({pnl_pct:+.2f}%)')

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
                        }
                        self.trade_log.append(trade_record)

                        # ✅ WRITE TRADE TO CSV IMMEDIATELY - NO DATA LOSS!
                        with open(self.trade_log_file, 'a', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=[
                                'entry_time', 'exit_time', 'strike', 'option_type', 'expiry',
                                'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct'
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
        
        self.log(f'TRADE PROFIT: Gross {trade.pnl:.2f}, Net {trade.pnlcomm:.2f}')
    
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
            self.daily_strike = updated_strike

        option_type = 'CE' if self.daily_direction == 'CALL' else 'PE'
        
        # Log what we're looking for (every 30 min)
        if dt.minute % 30 == 0:
            expiry_str = self.daily_expiry.date() if self.daily_expiry else 'None'
            self.log(f'Checking entry: {option_type} {self.daily_strike}, Expiry={expiry_str}')
        
        # Calculate OI change
        current_oi, oi_change, oi_change_pct = self.params.oi_analyzer.calculate_oi_change(
            strike=self.daily_strike,
            option_type=option_type,
            timestamp=pd.Timestamp(dt),
            expiry_date=self.daily_expiry
        )
        
        if current_oi is None:
            # Log every 30 minutes to see the problem
            if dt.minute % 30 == 0:
                self.log(f'⚠️  No OI data found for {option_type} {self.daily_strike} at {pd.Timestamp(dt)}')
            return None
        
        # Check if OI is unwinding
        is_unwinding = self.params.oi_analyzer.is_unwinding(oi_change)
        
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

            # Calculate initial running totals from all available history
            option_history['typical_price'] = (
                option_history['high'] + option_history['low'] + option_history['close']
            ) / 3.0
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
                    # Calculate contribution from new bar(s) only
                    new_bars['typical_price'] = (
                        new_bars['high'] + new_bars['low'] + new_bars['close']
                    ) / 3.0
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
            return option_price
        
        return None
    
    def manage_positions(self, dt):
        """Manage open positions - update stops and check exits using OPTION PRICES"""
        # Don't check exits if we already have a pending exit order
        if self.pending_exit or self.current_position is None:
            return

        pos_info = self.current_position

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

        # ALWAYS check initial stop loss first (for short positions, trigger when price goes UP)
        if current_price >= pos_info['stop_loss']:
            self.log(f'🛑 STOP LOSS HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, Stop: ₹{pos_info["stop_loss"]:.2f}')
            # Store the theoretical exit price (stop loss price) for accurate P&L calculation
            pos_info['stop_loss_triggered_price'] = current_price
            self.close()
            self.pending_exit = True  # Mark that we have a pending exit
            return  # Exit immediately, don't process more positions

        # Update lowest price (for short positions, profit increases as price decreases)
        if current_price < pos_info['lowest_price']:
            pos_info['lowest_price'] = current_price

        # Check if profit threshold reached (for shorts: profit when price drops)
        profit_pct = (entry_price - current_price) / entry_price
        if profit_pct >= (self.params.profit_threshold - 1):
            # Activate trailing stop (for shorts: lock in profit as price goes down)
            trailing_stop = pos_info['lowest_price'] * (1 + self.params.trailing_stop_pct)
            pos_info['trailing_stop'] = trailing_stop

            # Check trailing stop (for shorts: exit if price rises back up)
            if current_price >= trailing_stop:
                self.log(f'📉 TRAILING STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{trailing_stop:.2f}')
                # Store the theoretical exit price for accurate P&L calculation
                pos_info['trailing_stop_triggered_price'] = current_price
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
                # Place buy order
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
