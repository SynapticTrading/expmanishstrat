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

    def __init__(self, config, broker: PaperBroker, oi_analyzer: OIAnalyzer, state_manager=None):
        """
        Initialize strategy

        Args:
            config: Strategy configuration dict
            broker: PaperBroker instance
            oi_analyzer: OIAnalyzer instance
            state_manager: StateManager instance (optional)
        """
        self.config = config
        self.broker = broker
        self.oi_analyzer = oi_analyzer
        self.state_manager = state_manager

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
        self.lot_size = market_cfg['option_lot_size']
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
            self.daily_trade_taken = False
            self.vwap_running_totals = {}  # Reset VWAP for new day

            # Determine direction based on max OI buildup
            try:
                # Get expiry from first option in chain
                if not options_data.empty and 'expiry' in options_data.columns:
                    self.daily_expiry = options_data.iloc[0]['expiry']
                else:
                    print(f"[{current_time}] ✗ No expiry in options data")
                    self.daily_direction = None
                    return

                # Calculate max OI buildup from current options data
                max_call_strike, max_put_strike, call_distance, put_distance = \
                    self.oi_analyzer.calculate_max_oi_buildup(options_data, spot_price)

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
                self.daily_strike = self.oi_analyzer.get_nearest_strike(
                    spot_price, self.daily_direction, strikes
                )

                if self.daily_strike is None:
                    print(f"[{current_time}] ✗ Could not find suitable strike")
                    self.daily_direction = None
                    return

                print(f"[{current_time}] ✓ Daily Analysis Complete: Direction={self.daily_direction}, Strike={self.daily_strike}, Expiry={self.daily_expiry}, Spot={spot_price:.2f}")

                # Update strategy state
                if self.state_manager:
                    self.state_manager.update_strategy_state(
                        spot=spot_price,
                        strike=self.daily_strike,
                        direction=self.daily_direction,
                        call_strike=max_call_strike,
                        put_strike=max_put_strike,
                        vwap_tracking=self.vwap_running_totals
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
                vwap_tracking=self.vwap_running_totals
            )
            self.state_manager.save()

    def _check_entry(self, current_time, spot_price, options_data):
        """Check if entry conditions are met"""

        # Skip if already have max positions
        if len(self.broker.get_open_positions()) >= self.max_positions:
            return

        # Skip if already took trade today
        if self.daily_trade_taken:
            return

        # Skip if no direction determined
        if not self.daily_direction or not self.daily_strike:
            return

        # Check if strike needs updating based on spot price
        strikes = options_data['strike'].unique()
        new_strike = self.oi_analyzer.get_nearest_strike(
            spot_price, self.daily_direction, strikes
        )

        if new_strike != self.daily_strike and new_strike is not None:
            old_strike = self.daily_strike
            self.daily_strike = new_strike
            print(f"[{current_time}] 📍 STRIKE UPDATED: {old_strike} → {new_strike} (Spot: {spot_price:.2f})")
            # Reset entry OI when strike changes
            if hasattr(self, 'entry_oi'):
                delattr(self, 'entry_oi')
            # Reset VWAP tracking when strike changes
            if hasattr(self, 'vwap_initialized'):
                self.vwap_initialized = False

        # Get option data for daily strike
        option_data = self._get_option_data(
            options_data,
            self.daily_strike,
            self.daily_direction,
            self.daily_expiry
        )

        if option_data is None:
            return

        # Extract data
        option_price = option_data['close']
        option_oi = option_data['OI']  # Uppercase to match data format
        option_volume = option_data['volume']

        # Calculate VWAP
        vwap = self._calculate_vwap(
            self.daily_strike,
            self.daily_direction,
            self.daily_expiry,
            option_price,
            option_volume
        )

        # Log VWAP initialization
        if vwap and not getattr(self, 'vwap_initialized', False):
            # Calculate bars from 9:15 AM
            market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
            bars_count = int((current_time - market_open).total_seconds() / 300) + 1  # 300s = 5min

            # Check if this is a new day for VWAP
            if not hasattr(self, 'vwap_reset_date') or self.vwap_reset_date != current_time.date():
                print(f"[{current_time}] 🔄 Reset VWAP running totals for new day: {current_time.date()}")
                self.vwap_reset_date = current_time.date()

            print(f"[{current_time}] 🎯 Initialized VWAP for {self.daily_direction} {self.daily_strike}: {bars_count} bars from 9:15 AM")
            self.vwap_initialized = True

        # Calculate OI change
        # Note: For paper trading, we calculate from current options data instead
        # since we don't have historical OI snapshots
        current_oi_data = self._get_option_data(
            options_data,
            self.daily_strike,
            self.daily_direction,
            self.daily_expiry
        )

        if current_oi_data is not None:
            current_oi = current_oi_data['OI']
            # For paper trading, use entry OI if we have it, otherwise assume 0 change
            if hasattr(self, 'entry_oi'):
                oi_change = current_oi - self.entry_oi
                oi_change_pct = (oi_change / self.entry_oi * 100) if self.entry_oi > 0 else 0
            else:
                # First check - save as baseline
                self.entry_oi = current_oi
                oi_change_pct = 0
                oi_change = 0
        else:
            oi_change_pct = 0
            oi_change = 0

        # Check entry conditions
        # 1. OI unwinding (decreasing)
        is_unwinding = oi_change_pct < 0  # Negative change = unwinding

        # 2. Price above VWAP
        price_above_vwap = option_price > vwap if vwap else False

        # Display direction (already in CALL/PUT format)
        display_type = self.daily_direction

        # Detailed logging like backtest
        print(f"[{current_time}] Checking entry: {display_type} {self.daily_strike}, Expiry={self.daily_expiry}")

        # Show OI status with BUILDING/UNWINDING
        oi_status = "UNWINDING ✓" if is_unwinding else "BUILDING"
        print(f"[{current_time}] {display_type} {self.daily_strike}: OI={option_oi:,.0f}, Change={oi_change:,.0f} ({oi_change_pct:+.2f}%) - {oi_status}")

        # Show price vs VWAP check (only if VWAP is initialized)
        if vwap:
            vwap_status = "ABOVE ✓" if price_above_vwap else "BELOW ✗"
            print(f"[{current_time}] {display_type} {self.daily_strike}: Price=₹{option_price:.2f}, VWAP=₹{vwap:.2f} - {vwap_status}")

        # Enter trade if conditions met
        if is_unwinding and price_above_vwap:
            print(f"[{current_time}] 🎯 ENTRY SIGNAL: {display_type} {self.daily_strike} - Price: {option_price:.2f}, VWAP: {vwap:.2f}, OI Change: {oi_change:,.0f} ({oi_change_pct:.2f}%)")
            print(f"[{current_time}] 📈 PLACING BUY ORDER: size=1, expected_price={option_price:.2f}")

            # Execute buy order
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
                print(f"[{current_time}] 🔵 BUY OPTION EXECUTED: {display_type} {self.daily_strike} @ ₹{option_price:.2f} (Expiry: {self.daily_expiry}, 1 lot = {self.lot_size} qty)")
                print(f"[{current_time}]    📊 ENTRY DATA: VWAP={vwap:.2f}, OI={option_oi:,.0f}, OI Change={oi_change:,.0f} ({oi_change_pct:.2f}%)")

    def _check_exits(self, current_time, options_data):
        """Check exit conditions for all open positions"""

        positions = self.broker.get_open_positions()

        for position in positions.copy():  # Use copy to avoid modification during iteration
            # Get current option data
            option_data = self._get_option_data(
                options_data,
                position.strike,
                position.option_type,
                position.expiry
            )

            if option_data is None:
                continue

            # Extract data
            current_price = option_data['close']
            current_oi = option_data['OI']  # Uppercase to match data format
            current_volume = option_data['volume']

            # Calculate VWAP
            vwap = self._calculate_vwap(
                position.strike,
                position.option_type,
                position.expiry,
                current_price,
                current_volume
            )

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
            if pnl_pct < 0:
                oi_change_pct = (current_oi / position.oi_at_entry - 1)
                print(f"    OI Change: {oi_change_pct*100:+.2f}% (Threshold: {self.oi_increase_stop_pct*100:.0f}%)")

            # Trailing stop info (if active)
            if position.trailing_stop_active:
                trailing_stop_price = position.peak_price * (1 - self.trailing_stop_pct)
                print(f"    🎯 Trailing: Active | Peak: ₹{position.peak_price:.2f} | Stop: ₹{trailing_stop_price:.2f}")

            exit_reason = None

            # 1. Initial stop loss (25%)
            if current_price <= stop_loss_price:
                exit_reason = f"Stop Loss ({self.initial_stop_loss_pct*100:.0f}%)"

            # 2. VWAP stop (only in loss)
            elif pnl_pct < 0 and vwap:
                vwap_stop_price = vwap * (1 - self.vwap_stop_pct)
                if current_price <= vwap_stop_price:
                    exit_reason = f"VWAP Stop (>{self.vwap_stop_pct*100:.0f}% below VWAP)"

            # 3. OI increase stop (only in loss)
            elif pnl_pct < 0:
                oi_change_pct = (current_oi / position.oi_at_entry - 1)
                if oi_change_pct > self.oi_increase_stop_pct:
                    exit_reason = f"OI Increase Stop ({oi_change_pct*100:+.1f}%)"

            # 4. Trailing stop (only if activated)
            elif position.trailing_stop_active:
                trailing_stop_price = position.peak_price * (1 - self.trailing_stop_pct)
                if current_price <= trailing_stop_price:
                    exit_reason = f"Trailing Stop ({self.trailing_stop_pct*100:.0f}%)"

            # Execute exit if reason found
            if exit_reason:
                print(f"[{current_time}] EXIT SIGNAL: {exit_reason}")
                self.broker.sell(position, current_price, vwap, current_oi, exit_reason)

    def _force_eod_exit(self, current_time, options_data):
        """Force exit all positions at end of day"""

        positions = self.broker.get_open_positions()

        if positions:
            print(f"[{current_time}] Forcing EOD exit for {len(positions)} position(s)")

            for position in positions.copy():
                # Get current option data
                option_data = self._get_option_data(
                    options_data,
                    position.strike,
                    position.option_type,
                    position.expiry
                )

                if option_data is None:
                    continue

                current_price = option_data['close']
                current_oi = option_data['OI']  # Uppercase to match data format
                current_volume = option_data['volume']

                vwap = self._calculate_vwap(
                    position.strike,
                    position.option_type,
                    position.expiry,
                    current_price,
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

            mask = (
                (options_data['strike'] == strike) &
                (options_data['option_type'] == option_type_filter) &
                (options_data['expiry'] == expiry)
            )
            data = options_data[mask]

            if len(data) == 0:
                return None

            return data.iloc[0]

        except Exception as e:
            print(f"Error getting option data: {e}")
            return None

    def _calculate_vwap(self, strike, option_type, expiry, price, volume):
        """
        Calculate incremental VWAP for option

        Args:
            strike: Strike price
            option_type: CALL or PUT
            expiry: Expiry date
            price: Current price
            volume: Current volume

        Returns:
            float: VWAP value
        """
        key = (strike, option_type, expiry)

        # Initialize if first time
        if key not in self.vwap_running_totals:
            self.vwap_running_totals[key] = {'tpv': 0.0, 'volume': 0.0}

        # Calculate typical price
        typical_price = price  # Using close as typical price (can be (H+L+C)/3 if OHLC available)

        # Update running totals
        self.vwap_running_totals[key]['tpv'] += typical_price * volume
        self.vwap_running_totals[key]['volume'] += volume

        # Calculate VWAP
        if self.vwap_running_totals[key]['volume'] > 0:
            vwap = self.vwap_running_totals[key]['tpv'] / self.vwap_running_totals[key]['volume']
            return vwap
        else:
            return price  # Fallback to current price if no volume

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
