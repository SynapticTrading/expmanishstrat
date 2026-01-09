"""
Paper Trading Broker - Simulates order execution without real money
"""

from datetime import datetime
from typing import Dict, Optional
import csv
from pathlib import Path


class PaperPosition:
    """Represents a simulated position"""

    def __init__(self, strike, option_type, expiry, entry_price, size, entry_time,
                 vwap_at_entry, oi_at_entry, oi_change_at_entry):
        self.strike = strike
        self.option_type = option_type
        self.expiry = expiry
        self.entry_price = entry_price
        self.size = size
        self.entry_time = entry_time
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
        self.pnl = 0.0
        self.pnl_pct = 0.0


class PaperBroker:
    """Simulates broker for paper trading"""

    def __init__(self, initial_capital=100000, state_manager=None, logs_dir=None, broker_name=None):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = []
        self.trade_history = []
        self.state_manager = state_manager
        self.broker_name = broker_name or "Unknown"  # Track which broker this is

        # Setup daily trade log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Use provided logs_dir or fall back to relative path
        if logs_dir:
            logs_path = Path(logs_dir)
        else:
            logs_path = Path('paper_trading/logs')

        logs_path.mkdir(parents=True, exist_ok=True)

        self.daily_trade_log = logs_path / f'trades_{timestamp}.csv'
        self.cumulative_trade_log = logs_path / 'trades_cumulative.csv'

        # CSV fieldnames (added 'broker' column for multi-broker tracking)
        self.csv_fieldnames = [
            'entry_time', 'exit_time', 'broker', 'strike', 'option_type', 'expiry',
            'entry_price', 'exit_price', 'size', 'pnl', 'pnl_pct',
            'vwap_at_entry', 'vwap_at_exit', 'oi_at_entry', 'oi_change_at_entry',
            'oi_at_exit', 'exit_reason'
        ]

        # Write header to daily CSV
        with open(self.daily_trade_log, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
            writer.writeheader()

        # Create cumulative CSV if it doesn't exist (with header)
        if not self.cumulative_trade_log.exists():
            with open(self.cumulative_trade_log, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_fieldnames)
                writer.writeheader()

        print(f"[{datetime.now()}] Paper Broker initialized with capital: ₹{initial_capital:,.2f}")
        print(f"[{datetime.now()}] Daily trade log: {self.daily_trade_log}")
        print(f"[{datetime.now()}] Cumulative trade log: {self.cumulative_trade_log}")

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
            position = PaperPosition(
                strike=trade_data.get('strike', 0),
                option_type=trade_data.get('option_type', 'CALL'),
                expiry=trade_data.get('expiry', ''),
                entry_price=trade_data.get('entry_price', 0),
                size=trade_data.get('size', 75),
                entry_time=datetime.fromisoformat(trade_data['entry_time']) if isinstance(trade_data.get('entry_time'), str) else trade_data.get('entry_time', datetime.now()),
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

            print(f"  ✓ Restored trade: {position.option_type} {position.strike} | P&L: ₹{position.pnl:+,.2f}")

        print(f"[{datetime.now()}] ✓ Restored {len(closed_positions)} closed trade(s)")

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

            # Reconstruct PaperPosition object
            position = PaperPosition(
                strike=pos_data['strike'],
                option_type=pos_data['option_type'],
                expiry=pos_data['expiry'],
                entry_price=entry.get('price', 0),
                size=entry.get('quantity', 0),
                entry_time=datetime.fromisoformat(entry['time']) if isinstance(entry.get('time'), str) else entry.get('time', datetime.now()),
                vwap_at_entry=market_data.get('entry_vwap', 0),
                oi_at_entry=market_data.get('entry_oi', 0),
                oi_change_at_entry=market_data.get('oi_change_pct', 0)
            )

            # Restore peak price and trailing stop state
            position.peak_price = price_tracking.get('peak_price', position.entry_price)
            position.trailing_stop_active = stop_losses.get('trailing_active', False)

            # Restore order_id if available
            if 'order_id' in pos_data:
                position.order_id = pos_data['order_id']

            self.positions.append(position)

            # NOTE: Do NOT deduct cash again - the state file's current_cash already has position costs deducted
            # The initial_capital we received already accounts for open positions

            print(f"  ✓ Restored: {position.option_type} {position.strike} @ ₹{position.entry_price:.2f}")
            print(f"     Size: {position.size}, Peak: ₹{position.peak_price:.2f}, Trailing: {position.trailing_stop_active}")

        print(f"[{datetime.now()}] ✓ Restored {len(saved_positions)} position(s)")
        print(f"[{datetime.now()}] Available cash: ₹{self.cash:,.2f}")

    def buy(self, strike, option_type, expiry, price, size, vwap, oi, oi_change):
        """Execute a buy order (paper trading)"""

        # Calculate cost
        cost = price * size

        if cost > self.cash:
            print(f"[{datetime.now()}] ✗ Insufficient cash for buy order")
            print(f"  Required: ₹{cost:,.2f}, Available: ₹{self.cash:,.2f}")
            return None

        # Create position
        position = PaperPosition(
            strike=strike,
            option_type=option_type,
            expiry=expiry,
            entry_price=price,
            size=size,
            entry_time=datetime.now(),
            vwap_at_entry=vwap,
            oi_at_entry=oi,
            oi_change_at_entry=oi_change
        )

        # Update cash
        self.cash -= cost
        self.positions.append(position)

        # Save to state
        if self.state_manager:
            order_id = self.state_manager.update_position_entry(position)
            position.order_id = order_id  # Store order_id in position

            # Update portfolio state
            positions_value = sum(p.entry_price * p.size for p in self.positions)
            self.state_manager.update_portfolio(self.initial_capital, self.cash, positions_value)
            self.state_manager.save()

        print(f"[{datetime.now()}] ✓ BUY ORDER EXECUTED")
        print(f"  Strike: {strike} {option_type}")
        print(f"  Expiry: {expiry}")
        print(f"  Entry Price: ₹{price:,.2f}")
        print(f"  Size: {size}")
        print(f"  Cost: ₹{cost:,.2f}")
        print(f"  VWAP: ₹{vwap:,.2f}")
        print(f"  OI: {oi:,.0f} (Change: {oi_change:+.2%})")
        print(f"  Remaining Cash: ₹{self.cash:,.2f}")

        return position

    def sell(self, position, price, vwap, oi, reason):
        """Execute a sell order (close position)"""

        if position not in self.positions:
            print(f"[{datetime.now()}] ✗ Position not found")
            return False

        # Calculate P&L
        proceeds = price * position.size
        cost = position.entry_price * position.size
        pnl = proceeds - cost
        pnl_pct = (price / position.entry_price - 1) * 100

        # Update position
        position.exit_price = price
        position.exit_time = datetime.now()
        position.exit_reason = reason
        position.pnl = pnl
        position.pnl_pct = pnl_pct

        # Update cash
        self.cash += proceeds

        # Move to history
        self.positions.remove(position)
        self.trade_history.append(position)

        # Log to file
        self._log_trade(position, vwap, oi)

        # Update state
        if self.state_manager and hasattr(position, 'order_id'):
            self.state_manager.update_position_exit(position.order_id, position)

            # Update portfolio state
            positions_value = sum(p.entry_price * p.size for p in self.positions)
            self.state_manager.update_portfolio(self.initial_capital, self.cash, positions_value)
            self.state_manager.save()

        print(f"[{datetime.now()}] ✓ SELL ORDER EXECUTED")
        print(f"  Strike: {position.strike} {position.option_type}")
        print(f"  Exit Price: ₹{price:,.2f}")
        print(f"  P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)")
        print(f"  Exit Reason: {reason}")
        print(f"  Cash: ₹{self.cash:,.2f}")

        return True

    def _log_trade(self, position, vwap_at_exit, oi_at_exit):
        """Log trade to both daily and cumulative CSV files"""
        trade_data = {
            'entry_time': position.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': position.exit_time.strftime('%Y-%m-%d %H:%M:%S'),
            'broker': self.broker_name,  # Track which broker made this trade
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
            'exit_reason': position.exit_reason
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
        """Get list of open positions"""
        return self.positions

    def get_portfolio_value(self, current_prices: Dict):
        """
        Calculate total portfolio value

        Args:
            current_prices: Dict with keys as (strike, option_type, expiry) and values as current prices
        """
        positions_value = 0
        for pos in self.positions:
            key = (pos.strike, pos.option_type, pos.expiry)
            if key in current_prices:
                positions_value += current_prices[key] * pos.size

        return self.cash + positions_value

    def get_statistics(self):
        """Get trading statistics (ONLY realized P&L from closed trades)"""
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
                'current_cash': self.cash,
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
            'current_cash': self.cash,
            'roi': (realized_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0
        }
