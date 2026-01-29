#!/usr/bin/env python3
"""
Test script to verify LiveBroker state management
Tests all field updates for entry and exit
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
import json
import tempfile
import shutil

# Import the classes we need to test
from paper_trading.core.live_broker import LiveBroker, LivePosition
from paper_trading.core.state_manager import StateManager

# Mock adapter for testing
class MockAdapter:
    def __init__(self, entry_price=207.0, exit_price=214.15):
        self.broker_name = "test_broker"
        self.order_counter = 1000000
        self.orders = {}  # Track orders by ID
        self.entry_price = entry_price  # Simulated entry fill price
        self.exit_price = exit_price    # Simulated exit fill price

    def place_order(self, order_request):
        # Simulate successful order placement
        from paper_trading.brokers.adapter.types import OrderResponse, OrderStatus, TransactionType
        self.order_counter += 1
        order_id = f"TEST_{self.order_counter}"

        # Determine fill price based on order type
        if order_request.price:
            # LIMIT order - use specified price
            fill_price = order_request.price
        else:
            # MARKET order - simulate realistic fill based on BUY/SELL
            if order_request.transaction_type == TransactionType.BUY:
                fill_price = self.entry_price
            else:  # SELL
                fill_price = self.exit_price

        # Store order details
        self.orders[order_id] = {
            'quantity': order_request.quantity,
            'price': fill_price,
            'status': OrderStatus.COMPLETE
        }

        return OrderResponse(
            success=True,
            order_id=order_id,
            status=OrderStatus.COMPLETE,
            message="Order placed successfully",
            filled_quantity=order_request.quantity,
            average_price=fill_price,
            timestamp=datetime.now()
        )

    def get_order(self, order_id):
        # Simulate order status check - return actual fill price
        from paper_trading.brokers.adapter.types import OrderResponse, OrderStatus

        if order_id in self.orders:
            order = self.orders[order_id]
            return OrderResponse(
                success=True,
                order_id=order_id,
                status=order['status'],
                filled_quantity=order['quantity'],
                average_price=order['price'],  # Return actual fill price
                timestamp=datetime.now()
            )

        # Fallback for unknown orders (shouldn't happen in test)
        return OrderResponse(
            success=True,
            order_id=order_id,
            status=OrderStatus.COMPLETE,
            filled_quantity=65,
            average_price=207.0,
            timestamp=datetime.now()
        )

def create_test_config():
    """Create a minimal config for testing"""
    return {
        'trading_mode': {
            'mode': 'live',
            'live_settings': {
                'product_type': 'INTRADAY',
                'order_type': 'MARKET',
                'require_confirmation': False
            }
        },
        'position_sizing': {
            'initial_capital': 100000
        }
    }

def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def validate_field(field_name, actual, expected, parent="", tolerance=None):
    """Validate a field value"""
    path = f"{parent}.{field_name}" if parent else field_name

    # Handle floating point comparison with tolerance
    if tolerance is not None and isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if abs(actual - expected) <= tolerance:
            print(f"  ✅ {path}: {actual}")
            return True
        else:
            print(f"  ❌ {path}: Expected {expected}, got {actual}")
            return False

    # Exact comparison
    if actual == expected:
        print(f"  ✅ {path}: {actual}")
        return True
    else:
        print(f"  ❌ {path}: Expected {expected}, got {actual}")
        return False

def test_live_broker_state():
    """Test LiveBroker state management"""

    print_section("LIVE BROKER STATE MANAGEMENT TEST")

    # Create temporary directory for state files
    temp_dir = tempfile.mkdtemp()
    print(f"\nTest state directory: {temp_dir}")

    try:
        # Setup
        print("\n[Step 1] Creating test components...")
        config = create_test_config()

        # Create mock adapter with test prices (entry: 207.0, exit: 214.15)
        mock_adapter = MockAdapter(entry_price=207.0, exit_price=214.15)

        state_manager = StateManager(state_dir=temp_dir, broker_name="test_broker")
        state_manager.initialize_session(mode="live")

        # Create LiveBroker with mock adapter
        broker = LiveBroker(
            adapter=mock_adapter,
            config=config,
            state_manager=state_manager,
            logs_dir=temp_dir
        )
        print("  ✓ Components created")

        # Test Entry
        print_section("TEST 1: ENTRY (BUY ORDER)")

        entry_data = {
            'strike': 25250,
            'option_type': 'CALL',
            'expiry': '2026-02-03',
            'price': 207.00,
            'size': 65,
            'vwap': 202.87,
            'oi': 4423250,
            'oi_change': -0.0382  # -3.82%
        }

        print(f"\nPlacing BUY order:")
        print(f"  Strike: {entry_data['strike']} {entry_data['option_type']}")
        print(f"  Price: ₹{entry_data['price']}")
        print(f"  Size: {entry_data['size']}")
        print(f"  VWAP: ₹{entry_data['vwap']}")
        print(f"  OI: {entry_data['oi']:,}")
        print(f"  OI Change: {entry_data['oi_change']:.2%}")

        position = broker.buy(**entry_data)

        if not position:
            print("\n❌ FAILED: buy() returned None")
            return False

        print(f"\n✓ Position created:")
        print(f"  State ID: {position.order_id}")
        print(f"  Broker Order ID: {position.broker_order_id}")

        # Load and validate state file
        state_manager.load()
        state = state_manager.state

        print("\n[Validating Entry State]")

        # Check active positions
        if len(state['active_positions']) != 1:
            print(f"❌ Expected 1 active position, got {len(state['active_positions'])}")
            return False

        pos_id = list(state['active_positions'].keys())[0]
        pos_data = state['active_positions'][pos_id]

        print(f"\nPosition ID: {pos_id}")

        # Validate all entry fields
        all_valid = True

        # Basic fields
        all_valid &= validate_field("order_id", pos_data.get('order_id'), pos_id)
        all_valid &= validate_field("broker_order_id", pos_data.get('broker_order_id'), position.broker_order_id)
        all_valid &= validate_field("mode", pos_data.get('mode'), "LIVE")
        all_valid &= validate_field("strike", pos_data.get('strike'), entry_data['strike'])
        all_valid &= validate_field("option_type", pos_data.get('option_type'), entry_data['option_type'])
        all_valid &= validate_field("expiry", pos_data.get('expiry'), entry_data['expiry'])
        all_valid &= validate_field("status", pos_data.get('status'), "OPEN")

        # Entry fields
        entry = pos_data.get('entry', {})
        all_valid &= validate_field("price", entry.get('price'), entry_data['price'], "entry")
        all_valid &= validate_field("quantity", entry.get('quantity'), entry_data['size'], "entry")

        # Market data
        market = pos_data.get('market_data', {})
        all_valid &= validate_field("entry_vwap", market.get('entry_vwap'), entry_data['vwap'], "market_data")
        all_valid &= validate_field("current_vwap", market.get('current_vwap'), entry_data['vwap'], "market_data")
        all_valid &= validate_field("entry_oi", market.get('entry_oi'), entry_data['oi'], "market_data")
        all_valid &= validate_field("current_oi", market.get('current_oi'), entry_data['oi'], "market_data")

        # OI change should be stored as percentage
        oi_change_pct = market.get('oi_change_pct', 0)
        expected_oi_pct = entry_data['oi_change'] * 100  # -3.82
        all_valid &= validate_field("oi_change_pct", oi_change_pct, expected_oi_pct, "market_data")

        # Daily stats (should still be 0 - only increments on exit)
        stats = state.get('daily_stats', {})
        all_valid &= validate_field("trades_today", stats.get('trades_today'), 0, "daily_stats")
        all_valid &= validate_field("current_positions", stats.get('current_positions'), 1, "daily_stats")

        if not all_valid:
            print("\n❌ ENTRY VALIDATION FAILED")
            return False

        print("\n✅ ENTRY VALIDATION PASSED")

        # Test Exit
        print_section("TEST 2: EXIT (SELL ORDER)")

        exit_data = {
            'position': position,
            'price': 214.15,
            'vwap': 214.50,
            'oi': 4500000,
            'reason': 'Trailing Stop (10%)'
        }

        print(f"\nPlacing SELL order:")
        print(f"  Exit Price: ₹{exit_data['price']}")
        print(f"  Exit VWAP: ₹{exit_data['vwap']}")
        print(f"  Exit OI: {exit_data['oi']:,}")
        print(f"  Reason: {exit_data['reason']}")

        success = broker.sell(**exit_data)

        if not success:
            print("\n❌ FAILED: sell() returned False")
            return False

        print(f"\n✓ Position closed")
        print(f"  Exit Broker Order ID: {position.exit_order_id}")
        print(f"  P&L: ₹{position.pnl:+,.2f} ({position.pnl_pct:+.2f}%)")

        # Reload and validate state file
        state_manager.load()
        state = state_manager.state

        print("\n[Validating Exit State]")

        # Check active positions (should be empty)
        if len(state['active_positions']) != 0:
            print(f"❌ Expected 0 active positions, got {len(state['active_positions'])}")
            return False
        print("  ✅ Active positions: 0 (cleared)")

        # Check closed positions
        if len(state['closed_positions']) != 1:
            print(f"❌ Expected 1 closed position, got {len(state['closed_positions'])}")
            return False

        closed_pos = state['closed_positions'][0]

        print(f"\nClosed Position:")

        # Validate all exit fields
        all_valid = True

        # IDs
        all_valid &= validate_field("order_id", closed_pos.get('order_id'), pos_id)
        all_valid &= validate_field("broker_order_id", closed_pos.get('broker_order_id'), position.broker_order_id)
        all_valid &= validate_field("exit_broker_order_id", closed_pos.get('exit_broker_order_id'), position.exit_order_id)
        all_valid &= validate_field("mode", closed_pos.get('mode'), "LIVE")

        # Entry/Exit prices
        all_valid &= validate_field("entry_price", closed_pos.get('entry_price'), entry_data['price'])
        all_valid &= validate_field("exit_price", closed_pos.get('exit_price'), exit_data['price'])
        all_valid &= validate_field("size", closed_pos.get('size'), entry_data['size'])

        # P&L (use tolerance for floating point comparison)
        expected_pnl = (exit_data['price'] - entry_data['price']) * entry_data['size']
        expected_pnl_pct = ((exit_data['price'] / entry_data['price']) - 1) * 100
        all_valid &= validate_field("pnl", closed_pos.get('pnl'), expected_pnl, tolerance=0.01)
        all_valid &= validate_field("pnl_pct", round(closed_pos.get('pnl_pct', 0), 2), round(expected_pnl_pct, 2))

        # Market data (VWAP)
        all_valid &= validate_field("vwap_at_entry", closed_pos.get('vwap_at_entry'), entry_data['vwap'])
        all_valid &= validate_field("vwap_at_exit", closed_pos.get('vwap_at_exit'), exit_data['vwap'])

        # Market data (OI)
        all_valid &= validate_field("oi_at_entry", closed_pos.get('oi_at_entry'), entry_data['oi'])
        all_valid &= validate_field("oi_change_at_entry", closed_pos.get('oi_change_at_entry'), entry_data['oi_change'] * 100)
        all_valid &= validate_field("oi_at_exit", closed_pos.get('oi_at_exit'), exit_data['oi'])

        # Exit reason
        all_valid &= validate_field("exit_reason", closed_pos.get('exit_reason'), exit_data['reason'])

        # Daily stats (should be incremented now)
        stats = state.get('daily_stats', {})
        all_valid &= validate_field("trades_today", stats.get('trades_today'), 1, "daily_stats")
        all_valid &= validate_field("current_positions", stats.get('current_positions'), 0, "daily_stats")
        all_valid &= validate_field("total_pnl_today", stats.get('total_pnl_today'), expected_pnl, "daily_stats", tolerance=0.01)
        all_valid &= validate_field("win_count", stats.get('win_count'), 1, "daily_stats")
        all_valid &= validate_field("loss_count", stats.get('loss_count'), 0, "daily_stats")

        if not all_valid:
            print("\n❌ EXIT VALIDATION FAILED")
            return False

        print("\n✅ EXIT VALIDATION PASSED")

        # Print final state file summary
        print_section("FINAL STATE FILE SUMMARY")

        state_file = Path(temp_dir) / f"trading_state_test_broker_{datetime.now().strftime('%Y%m%d')}.json"
        print(f"\nState file: {state_file}")
        print(f"File size: {state_file.stat().st_size} bytes")

        print("\nState structure:")
        print(f"  Mode: {state.get('mode')}")
        print(f"  Active positions: {len(state.get('active_positions', {}))}")
        print(f"  Closed positions: {len(state.get('closed_positions', []))}")
        print(f"  Trades today: {state.get('daily_stats', {}).get('trades_today')}")
        print(f"  Total P&L today: ₹{state.get('daily_stats', {}).get('total_pnl_today', 0):+,.2f}")

        print("\nClosed position details:")
        for key in ['order_id', 'broker_order_id', 'exit_broker_order_id', 'mode',
                    'entry_price', 'exit_price', 'pnl', 'exit_reason',
                    'vwap_at_entry', 'vwap_at_exit', 'oi_at_entry', 'oi_at_exit']:
            value = closed_pos.get(key, 'N/A')
            if isinstance(value, float) and key in ['pnl', 'vwap_at_entry', 'vwap_at_exit']:
                print(f"  {key}: ₹{value:,.2f}")
            elif isinstance(value, int) and key in ['oi_at_entry', 'oi_at_exit']:
                print(f"  {key}: {value:,}")
            else:
                print(f"  {key}: {value}")

        print_section("TEST RESULT: ALL VALIDATIONS PASSED ✅")

        # Save state file to project root for inspection
        test_result_file = Path(__file__).parent / "test_live_state_result.json"
        with open(state_file, 'r') as f:
            state_content = json.load(f)
        with open(test_result_file, 'w') as f:
            json.dump(state_content, f, indent=2)

        print(f"\nTest result saved to: {test_result_file}")
        print("You can inspect the full state file structure there.")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up temporary directory: {temp_dir}")
        except:
            pass

if __name__ == "__main__":
    print("\n" + "="*80)
    print("  LIVE TRADING STATE MANAGEMENT TEST SUITE")
    print("="*80)
    print("\nThis test validates:")
    print("  1. Entry state fields (broker_order_id, mode, VWAP, OI, OI change)")
    print("  2. Exit state fields (exit_broker_order_id, exit price, exit reason)")
    print("  3. Market data updates (VWAP/OI at entry and exit)")
    print("  4. Closed positions tracking")
    print("  5. Daily stats updates (trades_today, P&L, win/loss count)")
    print("")

    success = test_live_broker_state()

    if success:
        print("\n" + "🎉 "*20)
        print("ALL TESTS PASSED - LIVE STATE MANAGEMENT IS WORKING CORRECTLY!")
        print("🎉 "*20 + "\n")
        sys.exit(0)
    else:
        print("\n" + "❌ "*20)
        print("TESTS FAILED - PLEASE REVIEW THE ERRORS ABOVE")
        print("❌ "*20 + "\n")
        sys.exit(1)
