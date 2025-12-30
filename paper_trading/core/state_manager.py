"""
State Persistence Manager
Saves and loads trading state to/from JSON files
"""

import json
from datetime import datetime
from pathlib import Path
import pytz
import numpy as np


class StateManager:
    """Manages state persistence for paper trading"""

    def __init__(self, state_dir="paper_trading/state"):
        """
        Initialize state manager

        Args:
            state_dir: Directory to save state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # IST timezone
        self.ist = pytz.timezone('Asia/Kolkata')

        # Current state
        self.state = None
        self.state_file = None

    def get_ist_now(self):
        """Get current time in IST"""
        return datetime.now(self.ist)

    def get_ist_timestamp(self):
        """Get current IST timestamp as ISO string"""
        return self.get_ist_now().isoformat()

    def convert_to_native_types(self, obj):
        """
        Recursively convert numpy types to native Python types for JSON serialization

        Args:
            obj: Object to convert

        Returns:
            Object with native Python types
        """
        if isinstance(obj, dict):
            return {key: self.convert_to_native_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_to_native_types(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    def initialize_session(self, mode="paper"):
        """
        Initialize a new trading session

        Args:
            mode: 'paper' or 'live'

        Returns:
            dict: Initial state
        """
        now = self.get_ist_now()
        date_str = now.strftime('%Y%m%d')
        session_id = f"SESSION_{date_str}_{now.strftime('%H%M')}"

        # Create state file
        self.state_file = self.state_dir / f"trading_state_{date_str}.json"

        # Initialize state
        self.state = {
            "timestamp": self.get_ist_timestamp(),
            "date": now.strftime('%Y-%m-%d'),
            "session_id": session_id,
            "mode": mode,

            "active_positions": {},
            "closed_positions": [],

            "strategy_state": {
                "current_spot": None,
                "trading_strike": None,
                "direction": None,
                "max_call_oi_strike": None,
                "max_put_oi_strike": None,
                "last_oi_check": None,
                "vwap_tracking": {}
            },

            "daily_stats": {
                "trades_today": 0,
                "max_trades_allowed": 1,
                "max_concurrent_positions": 2,
                "current_positions": 0,
                "total_pnl_today": 0.0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0
            },

            "portfolio": {
                "initial_capital": 0.0,
                "current_cash": 0.0,
                "positions_value": 0.0,
                "total_value": 0.0,
                "total_return_pct": 0.0
            },

            "api_stats": {
                "calls_5min_loop": 0,
                "calls_1min_ltp": 0,
                "total_calls_today": 0,
                "last_api_call": None
            },

            "system_health": {
                "last_heartbeat": self.get_ist_timestamp(),
                "broker_connected": False,
                "data_feed_status": "IDLE",
                "ltp_loop_running": False,
                "strategy_loop_running": False
            }
        }

        # Save initial state
        self.save()

        print(f"[{self.get_ist_now()}] Session initialized: {session_id}")
        print(f"[{self.get_ist_now()}] State file: {self.state_file}")

        return self.state

    def update_position_entry(self, position):
        """
        Update state with new position entry

        Args:
            position: PaperPosition object
        """
        order_id = f"PAPER_{self.get_ist_now().strftime('%Y%m%d')}_{len(self.state['active_positions']) + 1:03d}"

        position_data = {
            "order_id": order_id,
            "symbol": f"NIFTY{position.expiry.strftime('%y%b').upper()}{int(position.strike)}{position.option_type}",
            "strike": position.strike,
            "option_type": position.option_type,
            "expiry": position.expiry.strftime('%Y-%m-%d'),

            "entry": {
                "price": position.entry_price,
                "time": position.entry_time.astimezone(self.ist).isoformat(),
                "quantity": position.size,
                "reason": "OI unwinding + Price above VWAP"
            },

            "stop_losses": {
                "initial_stop": position.entry_price * 0.75,
                "initial_stop_pct": 25,
                "vwap_stop": None,
                "vwap_stop_active": False,
                "oi_stop_active": False,
                "trailing_stop": None,
                "trailing_stop_pct": 10,
                "trailing_active": position.trailing_stop_active
            },

            "price_tracking": {
                "peak_price": position.peak_price,
                "peak_time": position.entry_time.astimezone(self.ist).isoformat(),
                "current_price": position.entry_price,
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0
            },

            "market_data": {
                "entry_oi": position.oi_at_entry,
                "current_oi": position.oi_at_entry,
                "oi_change_pct": position.oi_change_at_entry * 100,
                "entry_vwap": position.vwap_at_entry,
                "current_vwap": position.vwap_at_entry
            },

            "status": "OPEN"
        }

        self.state["active_positions"][order_id] = position_data
        self.state["daily_stats"]["current_positions"] = len(self.state["active_positions"])
        self.state["timestamp"] = self.get_ist_timestamp()

        self.save()

        return order_id

    def update_position_exit(self, order_id, position):
        """
        Update state with position exit

        Args:
            order_id: Order ID
            position: PaperPosition object
        """
        if order_id not in self.state["active_positions"]:
            return

        pos_data = self.state["active_positions"][order_id]

        # Add exit data
        entry_time = datetime.fromisoformat(pos_data["entry"]["time"])
        exit_time = position.exit_time.astimezone(self.ist)
        duration_minutes = int((exit_time - entry_time).total_seconds() / 60)

        pos_data["exit"] = {
            "price": position.exit_price,
            "time": exit_time.isoformat(),
            "reason": position.exit_reason,
            "duration_minutes": duration_minutes
        }

        pos_data["status"] = "CLOSED"
        pos_data["pnl"] = position.pnl
        pos_data["pnl_pct"] = position.pnl_pct

        # Move to closed positions
        closed_summary = {
            "order_id": order_id,
            "entry_time": pos_data["entry"]["time"],
            "exit_time": exit_time.isoformat(),
            "entry_price": pos_data["entry"]["price"],
            "exit_price": position.exit_price,
            "pnl": position.pnl,
            "exit_reason": position.exit_reason
        }
        self.state["closed_positions"].append(closed_summary)

        # Remove from active
        del self.state["active_positions"][order_id]

        # Update stats
        self.state["daily_stats"]["trades_today"] += 1
        self.state["daily_stats"]["current_positions"] = len(self.state["active_positions"])
        self.state["daily_stats"]["total_pnl_today"] += position.pnl

        if position.pnl > 0:
            self.state["daily_stats"]["win_count"] += 1
        else:
            self.state["daily_stats"]["loss_count"] += 1

        total_trades = self.state["daily_stats"]["trades_today"]
        if total_trades > 0:
            self.state["daily_stats"]["win_rate"] = (
                self.state["daily_stats"]["win_count"] / total_trades * 100
            )

        self.state["timestamp"] = self.get_ist_timestamp()

        self.save()

    def update_position_price(self, order_id, current_price, vwap, oi):
        """
        Update position price tracking

        Args:
            order_id: Order ID
            current_price: Current option price
            vwap: Current VWAP
            oi: Current OI
        """
        if order_id not in self.state["active_positions"]:
            return

        pos_data = self.state["active_positions"][order_id]
        entry_price = pos_data["entry"]["price"]

        # Update price tracking
        pos_data["price_tracking"]["current_price"] = current_price
        pos_data["price_tracking"]["unrealized_pnl"] = (
            (current_price - entry_price) * pos_data["entry"]["quantity"]
        )
        pos_data["price_tracking"]["unrealized_pnl_pct"] = (
            (current_price / entry_price - 1) * 100
        )

        # Update peak if needed
        if current_price > pos_data["price_tracking"]["peak_price"]:
            pos_data["price_tracking"]["peak_price"] = current_price
            pos_data["price_tracking"]["peak_time"] = self.get_ist_timestamp()

        # Update market data
        pos_data["market_data"]["current_oi"] = oi
        pos_data["market_data"]["current_vwap"] = vwap
        pos_data["market_data"]["oi_change_pct"] = (
            (oi / pos_data["market_data"]["entry_oi"] - 1) * 100
        )

        self.state["timestamp"] = self.get_ist_timestamp()

        # Save every minute (not every price update)
        # Will be called from 1-min loop

    def update_strategy_state(self, spot, strike, direction, call_strike, put_strike, vwap_tracking):
        """
        Update strategy state

        Args:
            spot: Current spot price
            strike: Trading strike
            direction: CALL or PUT
            call_strike: Max call OI strike
            put_strike: Max put OI strike
            vwap_tracking: VWAP tracking dict
        """
        self.state["strategy_state"]["current_spot"] = spot
        self.state["strategy_state"]["trading_strike"] = strike
        self.state["strategy_state"]["direction"] = direction
        self.state["strategy_state"]["max_call_oi_strike"] = call_strike
        self.state["strategy_state"]["max_put_oi_strike"] = put_strike
        self.state["strategy_state"]["last_oi_check"] = self.get_ist_timestamp()

        # Update VWAP tracking
        vwap_state = {}
        for key, totals in vwap_tracking.items():
            strike_key = f"{key[0]}{key[1]}"
            vwap_state[strike_key] = {
                "sum_typical_price_volume": totals['tpv'],
                "sum_volume": totals['volume'],
                "current_vwap": totals['tpv'] / totals['volume'] if totals['volume'] > 0 else 0,
                "last_update": self.get_ist_timestamp()
            }

        self.state["strategy_state"]["vwap_tracking"] = vwap_state
        self.state["timestamp"] = self.get_ist_timestamp()

    def update_portfolio(self, initial_capital, current_cash, positions_value):
        """Update portfolio state"""
        self.state["portfolio"]["initial_capital"] = initial_capital
        self.state["portfolio"]["current_cash"] = current_cash
        self.state["portfolio"]["positions_value"] = positions_value
        self.state["portfolio"]["total_value"] = current_cash + positions_value
        self.state["portfolio"]["total_return_pct"] = (
            (self.state["portfolio"]["total_value"] / initial_capital - 1) * 100
            if initial_capital > 0 else 0.0
        )
        self.state["timestamp"] = self.get_ist_timestamp()

    def update_api_stats(self, loop_type):
        """
        Update API call statistics

        Args:
            loop_type: '5min' or '1min'
        """
        if loop_type == '5min':
            self.state["api_stats"]["calls_5min_loop"] += 1
        elif loop_type == '1min':
            self.state["api_stats"]["calls_1min_ltp"] += 1

        self.state["api_stats"]["total_calls_today"] = (
            self.state["api_stats"]["calls_5min_loop"] +
            self.state["api_stats"]["calls_1min_ltp"]
        )
        self.state["api_stats"]["last_api_call"] = self.get_ist_timestamp()

    def update_system_health(self, broker_connected=None, data_feed_status=None,
                            ltp_loop_running=None, strategy_loop_running=None):
        """Update system health status"""
        if broker_connected is not None:
            self.state["system_health"]["broker_connected"] = broker_connected
        if data_feed_status is not None:
            self.state["system_health"]["data_feed_status"] = data_feed_status
        if ltp_loop_running is not None:
            self.state["system_health"]["ltp_loop_running"] = ltp_loop_running
        if strategy_loop_running is not None:
            self.state["system_health"]["strategy_loop_running"] = strategy_loop_running

        self.state["system_health"]["last_heartbeat"] = self.get_ist_timestamp()
        self.state["timestamp"] = self.get_ist_timestamp()

    def save(self):
        """Save state to JSON file"""
        if self.state_file and self.state:
            try:
                # Convert numpy types to native Python types before saving
                state_to_save = self.convert_to_native_types(self.state)
                with open(self.state_file, 'w') as f:
                    json.dump(state_to_save, f, indent=2)
            except Exception as e:
                print(f"[{self.get_ist_now()}] ✗ Error saving state: {e}")

    def load(self, date_str=None):
        """
        Load state from JSON file

        Args:
            date_str: Date string (YYYYMMDD), defaults to today

        Returns:
            dict: Loaded state or None
        """
        if date_str is None:
            date_str = self.get_ist_now().strftime('%Y%m%d')

        state_file = self.state_dir / f"trading_state_{date_str}.json"

        if not state_file.exists():
            return None

        try:
            with open(state_file, 'r') as f:
                self.state = json.load(f)
                self.state_file = state_file
                print(f"[{self.get_ist_now()}] ✓ State loaded from {state_file}")
                return self.state
        except Exception as e:
            print(f"[{self.get_ist_now()}] ✗ Error loading state: {e}")
            return None

    def get_latest_portfolio(self):
        """
        Get portfolio value from the most recent state file
        Used for carrying forward portfolio across trading days

        Returns:
            dict: Portfolio info with initial_capital, current_cash, total_pnl
                  or None if no previous state found
        """
        # Get all state files sorted by date (newest first)
        state_files = sorted(self.state_dir.glob("trading_state_*.json"), reverse=True)

        if not state_files:
            return None

        # Try to load the most recent state file
        for state_file in state_files:
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)

                portfolio = state.get('portfolio', {})
                daily_stats = state.get('daily_stats', {})

                # Return portfolio info
                return {
                    'previous_date': state.get('date'),
                    'initial_capital': portfolio.get('initial_capital', 100000),
                    'current_cash': portfolio.get('current_cash', 100000),
                    'total_value': portfolio.get('total_value', 100000),
                    'total_pnl': daily_stats.get('total_pnl_today', 0),
                    'trades_count': daily_stats.get('trades_today', 0),
                    'win_rate': daily_stats.get('win_rate', 0)
                }
            except Exception as e:
                print(f"[{self.get_ist_now()}] ⚠ Could not read {state_file}: {e}")
                continue

        return None

    def can_recover(self):
        """
        Check if state can be recovered (has active positions or recent activity)

        Returns:
            bool: True if recovery is possible
        """
        if not self.state:
            return False

        # Can recover if there are active positions
        if self.state.get("active_positions"):
            return True

        # Can recover if strategy state exists (VWAP tracking, direction, etc.)
        strategy_state = self.state.get("strategy_state", {})
        if strategy_state.get("trading_strike") is not None:
            return True

        return False

    def get_recovery_info(self):
        """
        Get recovery information

        Returns:
            dict: Recovery info with positions, strategy state, etc.
        """
        if not self.state:
            return None

        now = self.get_ist_now()
        last_heartbeat = self.state.get("system_health", {}).get("last_heartbeat")

        recovery_info = {
            "can_recover": self.can_recover(),
            "last_heartbeat": last_heartbeat,
            "crash_time": last_heartbeat,  # Approximate crash time
            "recovery_time": now.isoformat(),
            "downtime_minutes": None,

            "active_positions": self.state.get("active_positions", {}),
            "active_positions_count": len(self.state.get("active_positions", {})),

            "strategy_state": self.state.get("strategy_state", {}),
            "daily_stats": self.state.get("daily_stats", {}),
            "portfolio": self.state.get("portfolio", {}),
        }

        # Calculate downtime
        if last_heartbeat:
            try:
                crash_time = datetime.fromisoformat(last_heartbeat)
                downtime = now - crash_time
                recovery_info["downtime_minutes"] = int(downtime.total_seconds() / 60)
            except:
                pass

        return recovery_info

    def resume_session(self):
        """
        Resume session from saved state

        Returns:
            dict: Recovery info
        """
        if not self.state:
            print(f"[{self.get_ist_now()}] ✗ No state to resume from")
            return None

        recovery_info = self.get_recovery_info()

        print(f"\n{'='*80}")
        print(f"RESUMING SESSION FROM CRASH")
        print(f"{'='*80}")
        print(f"Crash Time: {recovery_info['crash_time']}")
        print(f"Recovery Time: {self.get_ist_now()}")
        print(f"Downtime: {recovery_info['downtime_minutes']} minutes")
        print(f"Active Positions: {recovery_info['active_positions_count']}")

        # Update session info
        self.state["system_health"]["last_heartbeat"] = self.get_ist_timestamp()
        self.state["system_health"]["recovered"] = True
        self.state["system_health"]["recovery_time"] = self.get_ist_timestamp()
        self.state["timestamp"] = self.get_ist_timestamp()

        # Save updated state
        self.save()

        print(f"✓ Session resumed successfully")
        print(f"{'='*80}\n")

        return recovery_info
