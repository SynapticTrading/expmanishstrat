"""
Live Trading Broker - Executes real orders via adapter
"""

from datetime import datetime
import csv
from pathlib import Path
import time

from paper_trading.brokers.adapter.types import (
    OrderRequest, OrderType, ProductType,
    Exchange, TransactionType, OrderStatus
)


class LivePosition:
    """Represents a live position (mirrors PaperPosition)"""

    def __init__(self, strike, option_type, expiry, entry_price, size, entry_time,
                 order_id, vwap_at_entry, oi_at_entry, oi_change_at_entry):
        self.strike = strike
        self.option_type = option_type
        self.expiry = expiry
        self.entry_price = entry_price
        self.size = size
        self.entry_time = entry_time
        self.broker_order_id = order_id  # Real broker order ID (e.g., 260129000523978)
        self.order_id = None  # State manager ID (e.g., LIVE_20260129_001) - set after state save
        self.vwap_at_entry = vwap_at_entry
        self.oi_at_entry = oi_at_entry
        self.oi_change_at_entry = oi_change_at_entry

        # Track peak for trailing stop
        self.peak_price = entry_price
        self.trailing_stop_active = False

        # Exit tracking
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.exit_order_id = None  # Broker order ID for exit
        self.pnl = 0.0
        self.pnl_pct = 0.0


class LiveBroker:
    """Executes real orders via adapter - mirrors PaperBroker interface"""

    def __init__(self, adapter, config, state_manager=None, logs_dir=None):
        self.adapter = adapter
        self.config = config
        self.state_manager = state_manager

        # Extract settings from config
        live_cfg = config['trading_mode']['live_settings']
        self.product_type = ProductType[live_cfg['product_type']]
        self.order_type = OrderType[live_cfg['order_type']]
        self.max_order_value = live_cfg.get('max_order_value', None)  # Optional
        self.max_daily_loss = live_cfg.get('max_daily_loss', None)    # Optional

        # Order fill settings (rate limit protection)
        self.order_timeout = live_cfg.get('order_timeout', 30)
        self.status_check_interval = live_cfg.get('status_check_interval', 2)
        self.max_status_retries = live_cfg.get('max_status_retries', 3)
        self.retry_initial_delay = live_cfg.get('retry_initial_delay', 2)

        # Position tracking
        self.positions = []  # Open positions
        self.trade_history = []  # Closed trades
        self.order_ids = {}  # {position_id: order_id}
        self.daily_realized_pnl = 0.0

        # Get initial capital for statistics
        self.initial_capital = config['position_sizing']['initial_capital']

        # Setup separate logs for live trades
        self._setup_logging(logs_dir)

        print(f"[{datetime.now()}] Live Broker initialized")
        print(f"[{datetime.now()}] Product Type: {self.product_type.value}")
        print(f"[{datetime.now()}] Order Type: {self.order_type.value}")

        if self.max_order_value:
            print(f"[{datetime.now()}] Max Order Value: ₹{self.max_order_value:,.2f}")
        else:
            print(f"[{datetime.now()}] Max Order Value: No limit (relying on strategy stop losses)")

        if self.max_daily_loss:
            print(f"[{datetime.now()}] Max Daily Loss: ₹{self.max_daily_loss:,.2f}")
        else:
            print(f"[{datetime.now()}] Max Daily Loss: No limit (relying on strategy stop losses)")

        print(f"[{datetime.now()}] Order Settings:")
        print(f"  - Fill timeout: {self.order_timeout}s")
        print(f"  - Status check interval: {self.status_check_interval}s (rate limit protection)")
        print(f"  - Max retries: {self.max_status_retries} (exponential backoff)")
        print(f"  - Initial retry delay: {self.retry_initial_delay}s")

        print(f"[{datetime.now()}] Live trade log: {self.daily_trade_log}")

    def _setup_logging(self, logs_dir):
        """Setup logging for live trades"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if logs_dir:
            logs_path = Path(logs_dir)
        else:
            logs_path = Path('paper_trading/logs')

        logs_path.mkdir(parents=True, exist_ok=True)

        self.daily_trade_log = logs_path / f'live_trades_{timestamp}.csv'
        self.cumulative_trade_log = logs_path / 'live_trades_cumulative.csv'

        # CSV fieldnames
        self.csv_fieldnames = [
            'entry_time', 'exit_time', 'strike', 'option_type', 'expiry',
            'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct',
            'vwap_at_entry', 'vwap_at_exit', 'oi_at_entry', 'oi_change_at_entry',
            'oi_at_exit', 'exit_reason', 'entry_order_id', 'exit_order_id'
        ]

        # Write header to daily CSV
        with open(self.daily_trade_log, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
            writer.writeheader()

        # Create cumulative CSV if it doesn't exist
        if not self.cumulative_trade_log.exists():
            with open(self.cumulative_trade_log, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
                writer.writeheader()

    def buy(self, strike, option_type, expiry, price, size, vwap, oi, oi_change):
        """Execute a live buy order"""
        # 1. Safety checks (optional - only if configured)
        order_value = price * size

        # Check max order value (if configured)
        if self.max_order_value and order_value > self.max_order_value:
            print(f"[{datetime.now()}] ✗ Order rejected: Value ₹{order_value:,.2f} exceeds max ₹{self.max_order_value:,.2f}")
            return None

        # Check daily loss limit (if configured)
        if self.max_daily_loss and abs(self.daily_realized_pnl) > self.max_daily_loss:
            print(f"[{datetime.now()}] ✗ Order rejected: Daily loss ₹{abs(self.daily_realized_pnl):,.2f} exceeds max ₹{self.max_daily_loss:,.2f}")
            return None

        # 2. Create OrderRequest
        # Convert option_type format: CALL→CE, PUT→PE
        adapter_option_type = 'CE' if option_type == 'CALL' else 'PE'

        order = OrderRequest(
            underlying="NIFTY",
            option_type=adapter_option_type,
            strike=int(strike),
            expiry=expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.BUY,
            order_type=self.order_type,
            quantity=size,
            price=price if self.order_type == OrderType.LIMIT else None,
            product_type=self.product_type
        )

        print(f"[{datetime.now()}] 🔴 PLACING LIVE BUY ORDER 🔴")
        print(f"  Strike: {strike} {option_type}")
        print(f"  Expiry: {expiry}")
        print(f"  Price: ₹{price:,.2f}")
        print(f"  Size: {size}")
        print(f"  Order Value: ₹{order_value:,.2f}")

        # 3. Place order via adapter
        response = self.adapter.place_order(order)
        if not response.success:
            print(f"[{datetime.now()}] ✗ Order placement failed: {response.message}")
            return None

        print(f"[{datetime.now()}] ✓ Order placed: {response.order_id}")

        # 4. Wait for fill (for MARKET orders)
        actual_price = price
        if self.order_type == OrderType.MARKET:
            filled = self._wait_for_fill(response.order_id, timeout=30)
            if not filled:
                print(f"[{datetime.now()}] ⚠️  Order not filled within timeout, attempting cancel...")
                self.adapter.cancel_order(response.order_id)
                return None

            # 5. Get actual fill price with retry logic
            print(f"[{datetime.now()}] Fetching fill price from broker...")
            order_status = self._get_order_with_retry(response.order_id)  # Uses config defaults

            if order_status and order_status.average_price:
                actual_price = order_status.average_price
                slippage = actual_price - price
                slippage_pct = (slippage / price) * 100 if price > 0 else 0

                print(f"[{datetime.now()}] ✓ Order filled at ₹{actual_price:.2f}")
                if abs(slippage) > 0.01:  # Show slippage if > 1 paisa
                    print(f"[{datetime.now()}]   Slippage: ₹{slippage:+.2f} ({slippage_pct:+.2f}%)")
            else:
                print(f"[{datetime.now()}] ⚠️  Could not get fill price after retries, using requested price ₹{price:.2f}")

        # 6. Create position object
        position = LivePosition(
            strike=strike,
            option_type=option_type,
            expiry=expiry,
            entry_price=actual_price,
            size=size,
            entry_time=datetime.now(),
            order_id=response.order_id,  # Real broker order ID
            vwap_at_entry=vwap,
            oi_at_entry=oi,
            oi_change_at_entry=oi_change
        )

        self.positions.append(position)

        # 7. Update state manager (stores with LIVE_ID and broker_order_id)
        if self.state_manager:
            state_order_id = self.state_manager.update_position_entry_live(
                position,
                broker_order_id=response.order_id  # Pass real broker ID
            )
            position.order_id = state_order_id  # Store state manager ID for later use
            self.state_manager.save()

        # 8. Log order
        print(f"[{datetime.now()}] ✓ [LIVE] BUY ORDER FILLED: {option_type} {strike} @ ₹{actual_price:.2f}")
        print(f"  Broker Order ID: {response.order_id}")
        print(f"  VWAP: ₹{vwap:,.2f}")
        print(f"  OI: {oi:,.0f} (Change: {oi_change:+.2%})")

        return position

    def sell(self, position, price, vwap, oi, reason):
        """Execute a live sell order to close position"""
        # 1. Duplicate sell protection
        if hasattr(position, '_sold') and position._sold:
            print(f"[{datetime.now()}] ⚠️  Position already sold (prevented duplicate)")
            return False
        position._sold = True

        if position not in self.positions:
            print(f"[{datetime.now()}] ✗ Position not found in active positions")
            position._sold = False
            return False

        # 2. Create sell order
        # Convert option_type format: CALL→CE, PUT→PE
        adapter_option_type = 'CE' if position.option_type == 'CALL' else 'PE'

        order = OrderRequest(
            underlying="NIFTY",
            option_type=adapter_option_type,
            strike=int(position.strike),
            expiry=position.expiry,
            exchange=Exchange.NFO,
            transaction_type=TransactionType.SELL,
            order_type=self.order_type,
            quantity=position.size,
            price=price if self.order_type == OrderType.LIMIT else None,
            product_type=self.product_type
        )

        print(f"[{datetime.now()}] 🔴 PLACING LIVE SELL ORDER 🔴")
        print(f"  Strike: {position.strike} {position.option_type}")
        print(f"  Exit Price: ₹{price:,.2f}")
        print(f"  Size: {position.size}")
        print(f"  Exit Reason: {reason}")

        # 3. Place order
        response = self.adapter.place_order(order)
        if not response.success:
            print(f"[{datetime.now()}] ✗ Sell order placement failed: {response.message}")
            position._sold = False
            return False

        print(f"[{datetime.now()}] ✓ Sell order placed: {response.order_id}")

        # 4. Wait for fill
        actual_exit_price = price
        if self.order_type == OrderType.MARKET:
            filled = self._wait_for_fill(response.order_id, timeout=30)
            if not filled:
                print(f"[{datetime.now()}] ✗ Sell order not filled within timeout")
                position._sold = False
                return False

            # 5. Get actual exit price with retry logic
            print(f"[{datetime.now()}] Fetching exit fill price from broker...")
            order_status = self._get_order_with_retry(response.order_id)  # Uses config defaults

            if order_status and order_status.average_price:
                actual_exit_price = order_status.average_price
                slippage = actual_exit_price - price
                slippage_pct = (slippage / price) * 100 if price > 0 else 0

                print(f"[{datetime.now()}] ✓ Sell order filled at ₹{actual_exit_price:.2f}")
                if abs(slippage) > 0.01:  # Show slippage if > 1 paisa
                    print(f"[{datetime.now()}]   Slippage: ₹{slippage:+.2f} ({slippage_pct:+.2f}%)")
            else:
                print(f"[{datetime.now()}] ⚠️  Could not get exit fill price after retries, using requested price ₹{price:.2f}")

        # 6. Calculate P&L
        proceeds = actual_exit_price * position.size
        cost = position.entry_price * position.size
        pnl = proceeds - cost
        pnl_pct = (actual_exit_price / position.entry_price - 1) * 100

        # 7. Update position
        position.exit_price = actual_exit_price
        position.exit_time = datetime.now()
        position.exit_reason = reason
        position.pnl = pnl
        position.pnl_pct = pnl_pct
        position.exit_order_id = response.order_id

        # 8. Update daily P&L
        self.daily_realized_pnl += pnl

        # 9. Move to history
        self.positions.remove(position)
        self.trade_history.append(position)

        # 10. Log to CSV
        self._log_trade(position, vwap, oi)

        # 11. Update state
        if self.state_manager and hasattr(position, 'order_id') and position.order_id:
            self.state_manager.update_position_exit_live(
                position.order_id,  # State manager ID (LIVE_xxx)
                position,
                exit_broker_order_id=response.order_id,  # Real exit broker order ID
                exit_vwap=vwap,
                exit_oi=oi
            )
            self.state_manager.save()

        print(f"[{datetime.now()}] ✓ [LIVE] SELL ORDER FILLED")
        print(f"  Broker Exit Order ID: {response.order_id}")
        print(f"  P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)")
        print(f"  Daily P&L: ₹{self.daily_realized_pnl:+,.2f}")

        return True

    def _get_order_with_retry(self, order_id, max_retries=None, initial_delay=None):
        """
        Get order status with exponential backoff retry for rate limit errors.

        Args:
            order_id: Order ID to fetch
            max_retries: Maximum number of retry attempts (uses config default if None)
            initial_delay: Initial delay in seconds (uses config default if None)

        Returns:
            OrderResponse or None
        """
        # Use config values as defaults
        if max_retries is None:
            max_retries = self.max_status_retries
        if initial_delay is None:
            initial_delay = self.retry_initial_delay

        delay = initial_delay

        for attempt in range(max_retries):
            try:
                order_status = self.adapter.get_order(order_id)

                if order_status:
                    return order_status

                # If None returned, might be rate limit - retry with backoff
                if attempt < max_retries - 1:
                    print(f"[{datetime.now()}] ⚠️  Order status fetch returned None, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff

            except Exception as e:
                error_msg = str(e).lower()

                # Check if it's a rate limit error
                if 'rate' in error_msg or 'access denied' in error_msg or 'too many' in error_msg:
                    if attempt < max_retries - 1:
                        print(f"[{datetime.now()}] ⚠️  Rate limit detected, backing off for {delay}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        print(f"[{datetime.now()}] ✗ Rate limit persists after {max_retries} attempts: {e}")
                        return None
                else:
                    # Non-rate-limit error, log and return None
                    print(f"[{datetime.now()}] ✗ Error fetching order status: {e}")
                    return None

        return None

    def _wait_for_fill(self, order_id, timeout=None):
        """
        Wait for order to be filled with rate limit handling.

        Args:
            order_id: Order ID to monitor
            timeout: Timeout in seconds (uses config default if None)

        Returns:
            bool: True if filled, False if timeout
        """
        # Use config values as defaults
        if timeout is None:
            timeout = self.order_timeout

        start_time = time.time()
        check_interval = self.status_check_interval  # From config (default 2s)
        last_check = 0

        while time.time() - start_time < timeout:
            # Rate limit protection: don't check too frequently
            elapsed = time.time() - last_check
            if elapsed < check_interval:
                time.sleep(check_interval - elapsed)

            last_check = time.time()

            # Use retry logic for order status fetch
            order_status = self._get_order_with_retry(order_id)  # Uses config defaults

            if order_status:
                if order_status.status == OrderStatus.COMPLETE:
                    return True
                elif order_status.status in [OrderStatus.REJECTED, OrderStatus.CANCELLED]:
                    print(f"[{datetime.now()}] ✗ Order {order_id} {order_status.status.value}")
                    return False
            else:
                # If we still can't get status after retries, continue waiting
                print(f"[{datetime.now()}] ⚠️  Could not get order status, will retry...")

        print(f"[{datetime.now()}] ⚠️  Timeout waiting for order fill after {timeout}s")
        return False

    def _log_trade(self, position, vwap_at_exit, oi_at_exit):
        """Log live trade to CSV (separate file from paper trades)"""
        trade_data = {
            'entry_time': position.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': position.exit_time.strftime('%Y-%m-%d %H:%M:%S'),
            'strike': position.strike,
            'option_type': position.option_type,
            'expiry': position.expiry,
            'entry_price': position.entry_price,
            'exit_price': position.exit_price,
            'size': position.size,
            'pnl': position.pnl,
            'pnl_pct': position.pnl_pct,
            'vwap_at_entry': position.vwap_at_entry,
            'vwap_at_exit': vwap_at_exit,
            'oi_at_entry': position.oi_at_entry,
            'oi_change_at_entry': position.oi_change_at_entry,
            'oi_at_exit': oi_at_exit,
            'exit_reason': position.exit_reason,
            'entry_order_id': position.order_id,
            'exit_order_id': getattr(position, 'exit_order_id', '')
        }

        # Write to daily CSV
        with open(self.daily_trade_log, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
            writer.writerow(trade_data)

        # Append to cumulative CSV
        with open(self.cumulative_trade_log, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
            writer.writerow(trade_data)

    def get_open_positions(self):
        """Get list of open positions (compatible with PaperBroker)"""
        return self.positions

    def get_statistics(self):
        """Get trading statistics (same format as PaperBroker)"""
        # Calculate realized P&L from closed trades ONLY
        if not self.trade_history:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'current_cash': 0.0,  # N/A for live trading
                'roi': 0.0
            }

        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.pnl > 0)
        losing_trades = sum(1 for t in self.trade_history if t.pnl <= 0)
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        # Only count realized P&L from closed trades
        realized_pnl = sum(t.pnl for t in self.trade_history)
        avg_pnl = realized_pnl / total_trades

        max_win = max((t.pnl for t in self.trade_history), default=0)
        max_loss = min((t.pnl for t in self.trade_history), default=0)

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': realized_pnl,
            'avg_pnl': avg_pnl,
            'max_win': max_win,
            'max_loss': max_loss,
            'current_cash': 0.0,  # N/A for live trading (use adapter.get_funds())
            'roi': (realized_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0
        }

    def restore_positions(self, saved_positions):
        """
        Restore positions from saved state during crash recovery

        Args:
            saved_positions: List of position dictionaries from state file
        """
        if not saved_positions:
            return

        print(f"[{datetime.now()}] Restoring {len(saved_positions)} position(s)...")

        for pos_data in saved_positions:
            # Extract nested fields from state file structure
            entry = pos_data.get('entry', {})
            price_tracking = pos_data.get('price_tracking', {})
            market_data = pos_data.get('market_data', {})
            stop_losses = pos_data.get('stop_losses', {})

            # Reconstruct LivePosition object
            position = LivePosition(
                strike=pos_data['strike'],
                option_type=pos_data['option_type'],
                expiry=pos_data['expiry'],
                entry_price=entry.get('price', 0),
                size=entry.get('quantity', 0),
                entry_time=datetime.fromisoformat(entry['time']) if isinstance(entry.get('time'), str) else entry.get('time', datetime.now()),
                order_id=pos_data.get('broker_order_id', ''),  # Broker order ID
                vwap_at_entry=market_data.get('entry_vwap', 0),
                oi_at_entry=market_data.get('entry_oi', 0),
                oi_change_at_entry=market_data.get('oi_change_pct', 0) / 100  # Convert back to decimal
            )

            # Restore both IDs
            position.order_id = pos_data.get('order_id', '')  # State manager ID
            position.broker_order_id = pos_data.get('broker_order_id', '')  # Broker order ID

            # Restore peak price and trailing stop state
            position.peak_price = price_tracking.get('peak_price', position.entry_price)
            position.trailing_stop_active = stop_losses.get('trailing_active', False)

            self.positions.append(position)

            print(f"  ✓ Restored: {position.option_type} {position.strike} @ ₹{position.entry_price:.2f}")
            print(f"     Broker Order ID: {position.broker_order_id}")
            print(f"     Size: {position.size}, Peak: ₹{position.peak_price:.2f}, Trailing: {position.trailing_stop_active}")

        print(f"[{datetime.now()}] ✓ Restored {len(saved_positions)} position(s)")

    def restore_trade_history(self, closed_positions):
        """
        Restore closed trades from saved state during crash recovery

        Args:
            closed_positions: List of closed trade dictionaries from state file
        """
        if not closed_positions:
            return

        print(f"[{datetime.now()}] Restoring {len(closed_positions)} closed trade(s)...")

        for trade_data in closed_positions:
            # Create a minimal position object for trade history
            position = LivePosition(
                strike=trade_data.get('strike', 0),
                option_type=trade_data.get('option_type', 'CALL'),
                expiry=trade_data.get('expiry', ''),
                entry_price=trade_data.get('entry_price', 0),
                size=trade_data.get('size', 75),
                entry_time=datetime.fromisoformat(trade_data['entry_time']) if isinstance(trade_data.get('entry_time'), str) else trade_data.get('entry_time', datetime.now()),
                order_id=trade_data.get('order_id', ''),
                vwap_at_entry=trade_data.get('vwap_at_entry', 0),
                oi_at_entry=trade_data.get('oi_at_entry', 0),
                oi_change_at_entry=trade_data.get('oi_change_at_entry', 0)
            )

            # Set exit data
            position.exit_price = trade_data.get('exit_price', 0)
            position.exit_time = datetime.fromisoformat(trade_data['exit_time']) if isinstance(trade_data.get('exit_time'), str) else trade_data.get('exit_time', datetime.now())
            position.exit_reason = trade_data.get('exit_reason', 'Unknown')
            position.pnl = trade_data.get('pnl', 0)
            position.pnl_pct = trade_data.get('pnl_pct', 0)

            self.trade_history.append(position)
            self.daily_realized_pnl += position.pnl

            print(f"  ✓ Restored trade: {position.option_type} {position.strike} | P&L: ₹{position.pnl:+,.2f}")

        print(f"[{datetime.now()}] ✓ Restored {len(closed_positions)} closed trade(s)")
        print(f"[{datetime.now()}] Daily P&L: ₹{self.daily_realized_pnl:+,.2f}")
