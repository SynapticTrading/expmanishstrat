#!/usr/bin/env python3
"""
Comprehensive End-to-End Test for State File Synchronization
Tests all dependencies: recovery, 1 trade/day, portfolio isolation, mode separation
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
import json
import tempfile
import shutil

from paper_trading.core.state_manager import StateManager
from paper_trading.core.live_broker import LiveBroker, LivePosition
from paper_trading.core.broker import PaperBroker
from paper_trading.brokers.adapter.types import OrderResponse, OrderStatus, TransactionType

def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

class MockAdapter:
    """Mock broker adapter for testing"""
    def __init__(self, mode="paper"):
        self.broker_name = "test_broker"
        self.order_counter = 1000000
        self.orders = {}
        self.mode = mode

    def place_order(self, order_request):
        from paper_trading.brokers.adapter.types import OrderResponse, OrderStatus, TransactionType
        self.order_counter += 1
        order_id = f"{self.mode.upper()}_{self.order_counter}"

        # Simulate fill
        if order_request.transaction_type == TransactionType.BUY:
            fill_price = 200.0 if self.mode == "paper" else 207.0
        else:
            fill_price = 210.0 if self.mode == "paper" else 215.0

        self.orders[order_id] = {
            'quantity': order_request.quantity,
            'price': fill_price,
            'status': OrderStatus.COMPLETE
        }

        return OrderResponse(
            success=True,
            order_id=order_id,
            status=OrderStatus.COMPLETE,
            message="Order placed",
            filled_quantity=order_request.quantity,
            average_price=fill_price,
            timestamp=datetime.now()
        )

    def get_order(self, order_id):
        from paper_trading.brokers.adapter.types import OrderResponse, OrderStatus
        if order_id in self.orders:
            order = self.orders[order_id]
            return OrderResponse(
                success=True,
                order_id=order_id,
                status=order['status'],
                filled_quantity=order['quantity'],
                average_price=order['price'],
                timestamp=datetime.now()
            )
        return None

def create_test_config():
    """Create minimal test config"""
    return {
        'trading_mode': {
            'mode': 'paper',
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

def test_end_to_end():
    """Comprehensive end-to-end test"""

    print_section("END-TO-END STATE SYNCHRONIZATION TEST")

    temp_dir = tempfile.mkdtemp()
    print(f"\nTest directory: {temp_dir}")

    try:
        all_passed = True

        # ========================================
        # TEST 1: Paper Mode Trade
        # ========================================
        print_section("TEST 1: PAPER MODE - CREATE TRADE")

        # Initialize paper mode
        paper_config = create_test_config()
        paper_config['trading_mode']['mode'] = 'paper'

        paper_state = StateManager(state_dir=temp_dir, broker_name="test")
        paper_state.initialize_session(mode="paper")

        paper_adapter = MockAdapter(mode="paper")
        paper_broker = PaperBroker(
            initial_capital=100000,
            state_manager=paper_state,
            logs_dir=temp_dir,
            broker_name="test"
        )

        # Place paper trade
        paper_pos = paper_broker.buy(
            strike=25000,
            option_type="CALL",
            expiry="2026-02-03",
            price=200.0,
            size=50,
            vwap=198.0,
            oi=3500000,
            oi_change=-0.03
        )

        if paper_pos:
            print(f"✅ Paper trade created: {paper_pos.order_id}")
        else:
            print(f"❌ Paper trade failed")
            all_passed = False

        # Verify paper state file exists
        date_str = datetime.now().strftime('%Y%m%d')
        paper_file = Path(temp_dir) / f"trading_state_test_paper_{date_str}.json"

        if paper_file.exists():
            print(f"✅ Paper state file exists: {paper_file.name}")
        else:
            print(f"❌ Paper state file missing")
            all_passed = False

        # ========================================
        # TEST 2: Live Mode Trade (Same Day)
        # ========================================
        print_section("TEST 2: LIVE MODE - CREATE SEPARATE TRADE")

        # Initialize live mode (separate state manager)
        live_config = create_test_config()
        live_config['trading_mode']['mode'] = 'live'

        live_state = StateManager(state_dir=temp_dir, broker_name="test")
        live_state.initialize_session(mode="live")

        live_adapter = MockAdapter(mode="live")
        live_broker = LiveBroker(
            adapter=live_adapter,
            config=live_config,
            state_manager=live_state,
            logs_dir=temp_dir
        )

        # Place live trade
        live_pos = live_broker.buy(
            strike=25250,
            option_type="CALL",
            expiry="2026-02-03",
            price=207.0,
            size=65,
            vwap=205.0,
            oi=4000000,
            oi_change=-0.05
        )

        if live_pos:
            print(f"✅ Live trade created: {live_pos.order_id}")
            print(f"   Broker order ID: {live_pos.broker_order_id}")
        else:
            print(f"❌ Live trade failed")
            all_passed = False

        # Verify live state file exists
        live_file = Path(temp_dir) / f"trading_state_test_live_{date_str}.json"

        if live_file.exists():
            print(f"✅ Live state file exists: {live_file.name}")
        else:
            print(f"❌ Live state file missing")
            all_passed = False

        # ========================================
        # TEST 3: Verify State Isolation
        # ========================================
        print_section("TEST 3: VERIFY STATE ISOLATION")

        # Load paper state
        with open(paper_file, 'r') as f:
            paper_content = json.load(f)

        # Load live state
        with open(live_file, 'r') as f:
            live_content = json.load(f)

        # Check paper state
        paper_positions = paper_content.get('active_positions', {})
        if len(paper_positions) == 1:
            print(f"✅ Paper state has 1 position")
        else:
            print(f"❌ Paper state has wrong count: {len(paper_positions)}")
            all_passed = False

        # Check live state
        live_positions = live_content.get('active_positions', {})
        if len(live_positions) == 1:
            print(f"✅ Live state has 1 position")
        else:
            print(f"❌ Live state has wrong count: {len(live_positions)}")
            all_passed = False

        # Verify no cross-contamination
        paper_pos_id = list(paper_positions.keys())[0]
        live_pos_id = list(live_positions.keys())[0]

        if paper_pos_id.startswith("PAPER_"):
            print(f"✅ Paper position ID format correct: {paper_pos_id}")
        else:
            print(f"❌ Paper position ID wrong format: {paper_pos_id}")
            all_passed = False

        if live_pos_id.startswith("LIVE_"):
            print(f"✅ Live position ID format correct: {live_pos_id}")
        else:
            print(f"❌ Live position ID wrong format: {live_pos_id}")
            all_passed = False

        # ========================================
        # TEST 4: Test Recovery (Paper Mode)
        # ========================================
        print_section("TEST 4: RECOVERY TEST - PAPER MODE")

        # Create fresh state manager and set mode
        recovery_paper = StateManager(state_dir=temp_dir, broker_name="test")
        recovery_paper.mode = "paper"  # CRITICAL: Set mode before load

        # Try to load
        loaded_state = recovery_paper.load()

        if loaded_state:
            print(f"✅ Paper recovery: State loaded successfully")
        else:
            print(f"❌ Paper recovery: Failed to load state")
            all_passed = False

        # Verify it loaded the paper state (not live)
        if loaded_state and loaded_state.get('mode') == 'paper':
            print(f"✅ Paper recovery: Correct mode loaded")
        else:
            print(f"❌ Paper recovery: Wrong mode: {loaded_state.get('mode') if loaded_state else 'None'}")
            all_passed = False

        # Check if can recover
        if recovery_paper.can_recover():
            print(f"✅ Paper recovery: can_recover() returns True")
        else:
            print(f"❌ Paper recovery: can_recover() returns False")
            all_passed = False

        # Get recovery info
        recovery_info = recovery_paper.get_recovery_info()
        if recovery_info and recovery_info['active_positions_count'] == 1:
            print(f"✅ Paper recovery: Recovered 1 active position")
        else:
            count = recovery_info['active_positions_count'] if recovery_info else 0
            print(f"❌ Paper recovery: Wrong position count: {count}")
            all_passed = False

        # ========================================
        # TEST 5: Test Recovery (Live Mode)
        # ========================================
        print_section("TEST 5: RECOVERY TEST - LIVE MODE")

        # Create fresh state manager and set mode
        recovery_live = StateManager(state_dir=temp_dir, broker_name="test")
        recovery_live.mode = "live"  # CRITICAL: Set mode before load

        # Try to load
        loaded_state = recovery_live.load()

        if loaded_state:
            print(f"✅ Live recovery: State loaded successfully")
        else:
            print(f"❌ Live recovery: Failed to load state")
            all_passed = False

        # Verify it loaded the live state (not paper)
        if loaded_state and loaded_state.get('mode') == 'live':
            print(f"✅ Live recovery: Correct mode loaded")
        else:
            print(f"❌ Live recovery: Wrong mode: {loaded_state.get('mode') if loaded_state else 'None'}")
            all_passed = False

        # Verify broker_order_id exists in live recovery
        if loaded_state:
            live_pos_data = list(loaded_state['active_positions'].values())[0]
            if 'broker_order_id' in live_pos_data:
                print(f"✅ Live recovery: broker_order_id present: {live_pos_data['broker_order_id']}")
            else:
                print(f"❌ Live recovery: broker_order_id missing")
                all_passed = False

        # ========================================
        # TEST 6: Close Trades and Verify Isolation
        # ========================================
        print_section("TEST 6: CLOSE TRADES - VERIFY trades_today ISOLATION")

        # Close paper trade
        paper_broker.sell(
            position=paper_pos,
            price=210.0,
            vwap=209.0,
            oi=3600000,
            reason="Test exit"
        )

        # Close live trade
        live_broker.sell(
            position=live_pos,
            price=215.0,
            vwap=214.0,
            oi=4100000,
            reason="Test exit"
        )

        # Reload states
        paper_state.load()
        live_state.load()

        # Check paper trades_today
        paper_trades = paper_state.state['daily_stats']['trades_today']
        if paper_trades == 1:
            print(f"✅ Paper state: trades_today = 1")
        else:
            print(f"❌ Paper state: trades_today = {paper_trades}")
            all_passed = False

        # Check live trades_today
        live_trades = live_state.state['daily_stats']['trades_today']
        if live_trades == 1:
            print(f"✅ Live state: trades_today = 1")
        else:
            print(f"❌ Live state: trades_today = {live_trades}")
            all_passed = False

        # Verify closed positions
        paper_closed = len(paper_state.state['closed_positions'])
        live_closed = len(live_state.state['closed_positions'])

        if paper_closed == 1:
            print(f"✅ Paper state: 1 closed position")
        else:
            print(f"❌ Paper state: {paper_closed} closed positions")
            all_passed = False

        if live_closed == 1:
            print(f"✅ Live state: 1 closed position")
        else:
            print(f"❌ Live state: {live_closed} closed positions")
            all_passed = False

        # ========================================
        # TEST 7: Portfolio Isolation
        # ========================================
        print_section("TEST 7: PORTFOLIO ISOLATION")

        paper_pnl = paper_state.state['daily_stats']['total_pnl_today']
        live_pnl = live_state.state['daily_stats']['total_pnl_today']

        print(f"\nPaper P&L: ₹{paper_pnl:+,.2f}")
        print(f"Live P&L: ₹{live_pnl:+,.2f}")

        # Paper: (210 - 200) * 50 = 500
        expected_paper_pnl = (210.0 - 200.0) * 50
        if abs(paper_pnl - expected_paper_pnl) < 0.01:
            print(f"✅ Paper P&L correct: ₹{paper_pnl:,.2f}")
        else:
            print(f"❌ Paper P&L wrong: Expected ₹{expected_paper_pnl:,.2f}, got ₹{paper_pnl:,.2f}")
            all_passed = False

        # Live: (215 - 207) * 65 = 520
        expected_live_pnl = (215.0 - 207.0) * 65
        if abs(live_pnl - expected_live_pnl) < 0.01:
            print(f"✅ Live P&L correct: ₹{live_pnl:,.2f}")
        else:
            print(f"❌ Live P&L wrong: Expected ₹{expected_live_pnl:,.2f}, got ₹{live_pnl:,.2f}")
            all_passed = False

        # ========================================
        # TEST 8: Latest Portfolio Retrieval by Mode
        # ========================================
        print_section("TEST 8: LATEST PORTFOLIO RETRIEVAL BY MODE")

        # Get latest paper portfolio
        paper_latest = paper_state.get_latest_portfolio()
        if paper_latest and abs(paper_latest['total_pnl'] - expected_paper_pnl) < 0.01:
            print(f"✅ Paper get_latest_portfolio: ₹{paper_latest['total_pnl']:+,.2f}")
        else:
            pnl = paper_latest['total_pnl'] if paper_latest else 0
            print(f"❌ Paper get_latest_portfolio wrong: ₹{pnl:+,.2f}")
            all_passed = False

        # Get latest live portfolio
        live_latest = live_state.get_latest_portfolio()
        if live_latest and abs(live_latest['total_pnl'] - expected_live_pnl) < 0.01:
            print(f"✅ Live get_latest_portfolio: ₹{live_latest['total_pnl']:+,.2f}")
        else:
            pnl = live_latest['total_pnl'] if live_latest else 0
            print(f"❌ Live get_latest_portfolio wrong: ₹{pnl:+,.2f}")
            all_passed = False

        # ========================================
        # SUMMARY
        # ========================================
        print_section("FILE STRUCTURE SUMMARY")

        all_files = sorted(Path(temp_dir).glob("trading_state_*.json"))
        print(f"\nTotal state files: {len(all_files)}")
        for f in all_files:
            with open(f, 'r') as fp:
                content = json.load(fp)
            mode = content.get('mode')
            active = len(content.get('active_positions', {}))
            closed = len(content.get('closed_positions', []))
            trades = content.get('daily_stats', {}).get('trades_today', 0)
            pnl = content.get('daily_stats', {}).get('total_pnl_today', 0)
            print(f"\n{f.name}:")
            print(f"  Mode: {mode}")
            print(f"  Active: {active}, Closed: {closed}")
            print(f"  Trades today: {trades}")
            print(f"  P&L: ₹{pnl:+,.2f}")

        if len(all_files) == 2:
            print(f"\n✅ Correct number of files: 2 (paper + live separate)")
        else:
            print(f"\n❌ Wrong number of files: {len(all_files)}")
            all_passed = False

        if all_passed:
            print_section("✅ ALL TESTS PASSED - SYSTEM FULLY SYNCHRONIZED")
            return True
        else:
            print_section("❌ SOME TESTS FAILED - SEE ERRORS ABOVE")
            return False

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up test directory: {temp_dir}")
        except:
            pass


if __name__ == "__main__":
    print("\n" + "="*80)
    print("  END-TO-END STATE SYNCHRONIZATION TEST")
    print("="*80)
    print("\nThis test validates:")
    print("  1. Paper and live modes create separate state files")
    print("  2. States don't cross-contaminate")
    print("  3. Recovery loads correct mode-specific state")
    print("  4. trades_today counter isolated per mode")
    print("  5. Portfolio P&L isolated per mode")
    print("  6. get_latest_portfolio() filters by mode")
    print("  7. Broker order IDs stored in live trades")
    print("  8. All state syncs work correctly")
    print("")

    success = test_end_to_end()

    if success:
        print("\n" + "🎉 "*20)
        print("ALL END-TO-END TESTS PASSED - SYSTEM FULLY SYNCHRONIZED!")
        print("🎉 "*20 + "\n")
        sys.exit(0)
    else:
        print("\n" + "❌ "*20)
        print("TESTS FAILED - PLEASE REVIEW THE ERRORS ABOVE")
        print("❌ "*20 + "\n")
        sys.exit(1)
