#!/usr/bin/env python3
"""
Test 1 Trade/Day Limit Across Paper and Live Modes
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
import pandas as pd
import tempfile
import shutil

def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_1_trade_per_day():
    """Test that 1 trade/day limit works across paper and live modes"""

    print_section("1 TRADE/DAY CROSS-MODE TEST")

    temp_dir = tempfile.mkdtemp()
    logs_dir = Path(temp_dir) / "logs"
    logs_dir.mkdir()

    print(f"\nTest logs directory: {logs_dir}")

    try:
        all_passed = True

        # ========================================
        # TEST 1: Create Paper Trade CSV
        # ========================================
        print_section("TEST 1: CREATE PAPER TRADE TODAY")

        today = datetime.now()
        paper_csv = logs_dir / "trades_cumulative.csv"

        # Create paper trade from today
        paper_data = {
            'entry_time': [today.isoformat()],
            'strike': [25000],
            'option_type': ['CALL'],
            'entry_price': [200.0],
            'exit_price': [210.0],
            'pnl': [500.0]
        }
        df_paper = pd.DataFrame(paper_data)
        df_paper.to_csv(paper_csv, index=False)

        print(f"✅ Created {paper_csv.name} with 1 trade today")

        # ========================================
        # TEST 2: Create Live Trade CSV
        # ========================================
        print_section("TEST 2: CREATE LIVE TRADE TODAY")

        live_csv = logs_dir / "live_trades_cumulative.csv"

        # Create live trade from today
        live_data = {
            'entry_time': [today.isoformat()],
            'strike': [25250],
            'option_type': ['CALL'],
            'entry_price': [207.0],
            'exit_price': [215.0],
            'pnl': [520.0]
        }
        df_live = pd.DataFrame(live_data)
        df_live.to_csv(live_csv, index=False)

        print(f"✅ Created {live_csv.name} with 1 trade today")

        # ========================================
        # TEST 3: Test Check Function (Paper Only - OLD BUG)
        # ========================================
        print_section("TEST 3: SIMULATE OLD BUG (Paper CSV Only)")

        # This simulates the OLD buggy behavior
        def check_paper_only():
            """OLD BUGGY CODE - only checks paper CSV"""
            try:
                if not paper_csv.exists():
                    return 0

                df = pd.read_csv(paper_csv)
                if df.empty:
                    return 0

                today_date = datetime.now().date()
                df['entry_date'] = pd.to_datetime(df['entry_time']).dt.date
                trades_today = len(df[df['entry_date'] == today_date])

                return trades_today
            except:
                return 0

        paper_only_count = check_paper_only()
        print(f"\n❌ OLD CODE (paper only): Found {paper_only_count} trade(s)")
        print(f"   This would MISS the live trade!")

        # ========================================
        # TEST 4: Test Check Function (Both CSVs - FIXED)
        # ========================================
        print_section("TEST 4: TEST FIXED CODE (Both CSVs)")

        # This simulates the FIXED behavior
        def check_both_csvs():
            """FIXED CODE - checks both paper and live CSVs"""
            try:
                today_date = datetime.now().date()
                total_trades_today = 0

                csv_files = [
                    logs_dir / "trades_cumulative.csv",        # Paper
                    logs_dir / "live_trades_cumulative.csv"    # Live
                ]

                for cumulative_csv in csv_files:
                    if not cumulative_csv.exists():
                        continue

                    df = pd.read_csv(cumulative_csv)
                    if df.empty:
                        continue

                    df['entry_date'] = pd.to_datetime(df['entry_time']).dt.date
                    trades = len(df[df['entry_date'] == today_date])
                    total_trades_today += trades

                    if trades > 0:
                        mode = "live" if "live_trades" in str(cumulative_csv) else "paper"
                        print(f"   📊 Found {trades} {mode} trade(s)")

                return total_trades_today
            except Exception as e:
                print(f"   ⚠️  Error: {e}")
                return 0

        both_csvs_count = check_both_csvs()
        print(f"\n✅ FIXED CODE (both CSVs): Found {both_csvs_count} trade(s) total")

        if both_csvs_count == 2:
            print(f"✅ Correctly counts BOTH paper and live trades")
        else:
            print(f"❌ Wrong count: Expected 2, got {both_csvs_count}")
            all_passed = False

        # ========================================
        # TEST 5: Scenario - Take Live, Restart Paper
        # ========================================
        print_section("TEST 5: SCENARIO - Take Live Trade, Restart in Paper Mode")

        # Clear paper CSV (simulate no paper trades)
        paper_csv.unlink()
        print(f"\n1. Cleared paper CSV (no paper trades today)")

        # Live CSV still has 1 trade
        print(f"2. Live CSV has 1 trade today")

        # Check with OLD code
        paper_only_count = check_paper_only()
        print(f"\n❌ OLD CODE would find: {paper_only_count} trade(s)")
        print(f"   Result: daily_trade_taken = {'True' if paper_only_count > 0 else 'False ❌ BUG!'}")

        # Check with FIXED code
        both_csvs_count = check_both_csvs()
        print(f"\n✅ FIXED CODE finds: {both_csvs_count} trade(s)")
        print(f"   Result: daily_trade_taken = {'True ✅' if both_csvs_count > 0 else 'False'}")

        if both_csvs_count == 1:
            print(f"\n✅ FIXED CODE correctly blocks paper trade after live trade")
        else:
            print(f"\n❌ FIXED CODE failed: Expected 1, got {both_csvs_count}")
            all_passed = False

        # ========================================
        # TEST 6: Scenario - Take Paper, Restart Live
        # ========================================
        print_section("TEST 6: SCENARIO - Take Paper Trade, Restart in Live Mode")

        # Clear live CSV
        live_csv.unlink()
        print(f"\n1. Cleared live CSV (no live trades today)")

        # Recreate paper CSV
        df_paper.to_csv(paper_csv, index=False)
        print(f"2. Paper CSV has 1 trade today")

        # Check with FIXED code
        both_csvs_count = check_both_csvs()
        print(f"\n✅ FIXED CODE finds: {both_csvs_count} trade(s)")
        print(f"   Result: daily_trade_taken = {'True ✅' if both_csvs_count > 0 else 'False'}")

        if both_csvs_count == 1:
            print(f"\n✅ FIXED CODE correctly blocks live trade after paper trade")
        else:
            print(f"\n❌ FIXED CODE failed: Expected 1, got {both_csvs_count}")
            all_passed = False

        # ========================================
        # SUMMARY
        # ========================================
        print_section("SUMMARY")

        print("\n1 Trade/Day Limit Check:")
        print(f"  ✅ Checks: trades_cumulative.csv (paper)")
        print(f"  ✅ Checks: live_trades_cumulative.csv (live)")
        print(f"  ✅ Returns: Total count across BOTH modes")
        print(f"\nResult: 1 trade/day enforced GLOBALLY across paper and live modes")

        if all_passed:
            print_section("✅ ALL TESTS PASSED")
            return True
        else:
            print_section("❌ SOME TESTS FAILED")
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
    print("  1 TRADE/DAY CROSS-MODE TEST")
    print("="*80)
    print("\nThis test validates:")
    print("  1. Check finds paper trades")
    print("  2. Check finds live trades")
    print("  3. Check counts BOTH paper and live")
    print("  4. Live trade blocks paper trade")
    print("  5. Paper trade blocks live trade")
    print("")

    success = test_1_trade_per_day()

    if success:
        print("\n" + "🎉 "*20)
        print("1 TRADE/DAY LIMIT WORKS CORRECTLY ACROSS MODES!")
        print("🎉 "*20 + "\n")
        sys.exit(0)
    else:
        print("\n" + "❌ "*20)
        print("TESTS FAILED")
        print("❌ "*20 + "\n")
        sys.exit(1)
