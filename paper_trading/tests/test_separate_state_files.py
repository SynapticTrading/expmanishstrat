#!/usr/bin/env python3
"""
Test script to verify separate state files for paper and live modes
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
import json
import tempfile
import shutil

from paper_trading.core.state_manager import StateManager

def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_separate_state_files():
    """Test that paper and live modes create separate state files"""

    print_section("SEPARATE STATE FILE TEST")

    # Create temporary directory for state files
    temp_dir = tempfile.mkdtemp()
    print(f"\nTest directory: {temp_dir}")

    try:
        all_passed = True

        # ========================================
        # TEST 1: Create Paper Mode State
        # ========================================
        print_section("TEST 1: CREATE PAPER MODE STATE")

        paper_state_manager = StateManager(state_dir=temp_dir, broker_name="angelone")
        paper_state_manager.initialize_session(mode="paper")

        # Simulate a paper trade
        paper_state_manager.state['active_positions']['PAPER_001'] = {
            'order_id': 'PAPER_001',
            'mode': 'PAPER',
            'strike': 25000,
            'entry_price': 100.0
        }
        paper_state_manager.state['daily_stats']['trades_today'] = 1
        paper_state_manager.save()

        # Check paper state file exists
        date_str = datetime.now().strftime('%Y%m%d')
        paper_file = Path(temp_dir) / f"trading_state_angelone_paper_{date_str}.json"

        if paper_file.exists():
            print(f"✅ Paper state file created: {paper_file.name}")
        else:
            print(f"❌ Paper state file NOT created: {paper_file.name}")
            all_passed = False

        # ========================================
        # TEST 2: Create Live Mode State
        # ========================================
        print_section("TEST 2: CREATE LIVE MODE STATE")

        live_state_manager = StateManager(state_dir=temp_dir, broker_name="angelone")
        live_state_manager.initialize_session(mode="live")

        # Simulate a live trade
        live_state_manager.state['active_positions']['LIVE_001'] = {
            'order_id': 'LIVE_001',
            'broker_order_id': '123456789',
            'mode': 'LIVE',
            'strike': 25250,
            'entry_price': 207.0
        }
        live_state_manager.state['daily_stats']['trades_today'] = 1
        live_state_manager.save()

        # Check live state file exists
        live_file = Path(temp_dir) / f"trading_state_angelone_live_{date_str}.json"

        if live_file.exists():
            print(f"✅ Live state file created: {live_file.name}")
        else:
            print(f"❌ Live state file NOT created: {live_file.name}")
            all_passed = False

        # ========================================
        # TEST 3: Verify Files Are Separate
        # ========================================
        print_section("TEST 3: VERIFY FILES ARE SEPARATE")

        # List all state files
        all_files = list(Path(temp_dir).glob("trading_state_*.json"))
        print(f"\nTotal state files created: {len(all_files)}")
        for f in all_files:
            print(f"  - {f.name}")

        if len(all_files) == 2:
            print(f"\n✅ Correct number of files (2): paper and live are separate")
        else:
            print(f"\n❌ Wrong number of files: Expected 2, got {len(all_files)}")
            all_passed = False

        # ========================================
        # TEST 4: Verify Paper State Content
        # ========================================
        print_section("TEST 4: VERIFY PAPER STATE CONTENT")

        with open(paper_file, 'r') as f:
            paper_content = json.load(f)

        print(f"\nPaper state mode: {paper_content.get('mode')}")
        print(f"Paper active positions: {len(paper_content.get('active_positions', {}))}")
        print(f"Paper trades today: {paper_content.get('daily_stats', {}).get('trades_today')}")

        if paper_content.get('mode') == 'paper':
            print("✅ Paper state has correct mode")
        else:
            print(f"❌ Paper state has wrong mode: {paper_content.get('mode')}")
            all_passed = False

        if 'PAPER_001' in paper_content.get('active_positions', {}):
            print("✅ Paper state has paper position")
        else:
            print("❌ Paper state missing paper position")
            all_passed = False

        if 'LIVE_001' not in paper_content.get('active_positions', {}):
            print("✅ Paper state does NOT have live position (good)")
        else:
            print("❌ Paper state contaminated with live position")
            all_passed = False

        # ========================================
        # TEST 5: Verify Live State Content
        # ========================================
        print_section("TEST 5: VERIFY LIVE STATE CONTENT")

        with open(live_file, 'r') as f:
            live_content = json.load(f)

        print(f"\nLive state mode: {live_content.get('mode')}")
        print(f"Live active positions: {len(live_content.get('active_positions', {}))}")
        print(f"Live trades today: {live_content.get('daily_stats', {}).get('trades_today')}")

        if live_content.get('mode') == 'live':
            print("✅ Live state has correct mode")
        else:
            print(f"❌ Live state has wrong mode: {live_content.get('mode')}")
            all_passed = False

        if 'LIVE_001' in live_content.get('active_positions', {}):
            print("✅ Live state has live position")
        else:
            print("❌ Live state missing live position")
            all_passed = False

        if 'PAPER_001' not in live_content.get('active_positions', {}):
            print("✅ Live state does NOT have paper position (good)")
        else:
            print("❌ Live state contaminated with paper position")
            all_passed = False

        # ========================================
        # TEST 6: Verify Load Isolates Correctly
        # ========================================
        print_section("TEST 6: VERIFY LOAD ISOLATION")

        # Create fresh state managers and load
        paper_loader = StateManager(state_dir=temp_dir, broker_name="angelone")
        paper_loader.mode = "paper"
        paper_loader.load()

        live_loader = StateManager(state_dir=temp_dir, broker_name="angelone")
        live_loader.mode = "live"
        live_loader.load()

        # Verify paper loader got paper state
        if paper_loader.state and paper_loader.state.get('mode') == 'paper':
            print("✅ Paper loader loaded paper state")
        else:
            print("❌ Paper loader loaded wrong state")
            all_passed = False

        # Verify live loader got live state
        if live_loader.state and live_loader.state.get('mode') == 'live':
            print("✅ Live loader loaded live state")
        else:
            print("❌ Live loader loaded wrong state")
            all_passed = False

        # Verify loaded data is correct
        if 'PAPER_001' in paper_loader.state.get('active_positions', {}):
            print("✅ Paper loader has paper position")
        else:
            print("❌ Paper loader missing paper position")
            all_passed = False

        if 'LIVE_001' in live_loader.state.get('active_positions', {}):
            print("✅ Live loader has live position")
        else:
            print("❌ Live loader missing live position")
            all_passed = False

        # ========================================
        # TEST 7: Verify Portfolio Isolation
        # ========================================
        print_section("TEST 7: VERIFY PORTFOLIO ISOLATION")

        # Update portfolios differently
        paper_state_manager.state['portfolio']['total_value'] = 105000
        paper_state_manager.state['daily_stats']['total_pnl_today'] = 5000
        paper_state_manager.save()

        live_state_manager.state['portfolio']['total_value'] = 98000
        live_state_manager.state['daily_stats']['total_pnl_today'] = -2000
        live_state_manager.save()

        # Get latest portfolio for each mode
        paper_portfolio = paper_state_manager.get_latest_portfolio()
        live_portfolio = live_state_manager.get_latest_portfolio()

        print(f"\nPaper P&L: ₹{paper_portfolio.get('total_pnl', 0):+,.2f}")
        print(f"Live P&L: ₹{live_portfolio.get('total_pnl', 0):+,.2f}")

        if paper_portfolio.get('total_pnl') == 5000:
            print("✅ Paper portfolio isolated correctly")
        else:
            print(f"❌ Paper portfolio contaminated: {paper_portfolio.get('total_pnl')}")
            all_passed = False

        if live_portfolio.get('total_pnl') == -2000:
            print("✅ Live portfolio isolated correctly")
        else:
            print(f"❌ Live portfolio contaminated: {live_portfolio.get('total_pnl')}")
            all_passed = False

        # ========================================
        # FINAL SUMMARY
        # ========================================
        print_section("FILE STRUCTURE SUMMARY")

        print("\nCreated state files:")
        for f in sorted(all_files):
            size = f.stat().st_size
            with open(f, 'r') as fp:
                content = json.load(fp)
            mode = content.get('mode')
            positions = len(content.get('active_positions', {}))
            print(f"\n  {f.name}")
            print(f"    Size: {size} bytes")
            print(f"    Mode: {mode}")
            print(f"    Active positions: {positions}")

        print_section("EXPECTED NAMING CONVENTION")
        print("\nPaper trading: trading_state_<broker>_paper_<date>.json")
        print("Live trading:  trading_state_<broker>_live_<date>.json")
        print("\nExamples:")
        print("  trading_state_angelone_paper_20260129.json")
        print("  trading_state_angelone_live_20260129.json")

        if all_passed:
            print_section("✅ ALL TESTS PASSED - STATE FILES ARE PROPERLY SEPARATED")
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
    print("  SEPARATE STATE FILE TEST SUITE")
    print("="*80)
    print("\nThis test validates:")
    print("  1. Paper and live modes create separate state files")
    print("  2. File naming includes mode: trading_state_<broker>_<mode>_<date>.json")
    print("  3. States don't contaminate each other")
    print("  4. Load operation isolates correctly")
    print("  5. Portfolio tracking is separate")
    print("")

    success = test_separate_state_files()

    if success:
        print("\n" + "🎉 "*20)
        print("ALL TESTS PASSED - STATE FILES ARE PROPERLY SEPARATED!")
        print("🎉 "*20 + "\n")
        sys.exit(0)
    else:
        print("\n" + "❌ "*20)
        print("TESTS FAILED - PLEASE REVIEW THE ERRORS ABOVE")
        print("❌ "*20 + "\n")
        sys.exit(1)
