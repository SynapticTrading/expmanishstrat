#!/usr/bin/env python3
"""
Toggle Between STRICT and NON-STRICT Stop Loss Execution

This script automatically switches between strict execution (exit at exact thresholds)
and non-strict execution (exit at current market price when threshold crossed).

Usage:
    python scripts/toggle_strict_execution.py --mode strict   # Enable strict execution
    python scripts/toggle_strict_execution.py --mode normal   # Disable strict execution (revert)
    python scripts/toggle_strict_execution.py --check         # Check current mode
"""

import sys
import argparse
from pathlib import Path


STRATEGY_FILE = Path(__file__).parent.parent / "strategies" / "intraday_momentum_oi.py"


def check_current_mode():
    """Check if strategy is currently in STRICT or NORMAL mode"""
    with open(STRATEGY_FILE, 'r') as f:
        content = f.read()

    if 'STRICT EXECUTION' in content:
        return 'STRICT'
    else:
        return 'NORMAL'


def revert_to_normal():
    """Revert from STRICT to NORMAL (original) execution"""
    print("Reverting to NORMAL (non-strict) execution mode...")

    with open(STRATEGY_FILE, 'r') as f:
        content = f.read()

    # Check if already in normal mode
    if 'STRICT EXECUTION' not in content:
        print("❌ Already in NORMAL mode. No changes needed.")
        return False

    # Revert INITIAL STOP LOSS
    content = content.replace(
        '''        # ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
        if current_price <= pos_info['stop_loss']:
            # ✅ STRICT EXECUTION: Exit at EXACTLY the 25% stop loss price
            strict_exit_price = pos_info['stop_loss']
            strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

            self.log(f'🛑 STOP LOSS HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, STRICT Exit: ₹{strict_exit_price:.2f} (exactly -25.0% SL), '
                    f'STRICT P&L: {strict_pnl_pct:.1f}%')

            # Store strict exit price for accurate P&L calculation
            pos_info['stop_loss_triggered_price'] = strict_exit_price''',
        '''        # ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
        if current_price <= pos_info['stop_loss']:
            self.log(f'🛑 STOP LOSS HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, Stop: ₹{pos_info["stop_loss"]:.2f}')
            # Store the theoretical exit price (stop loss price) for accurate P&L calculation
            pos_info['stop_loss_triggered_price'] = current_price'''
    )

    # Revert VWAP STOP
    content = content.replace(
        '''                    vwap_diff_pct = ((current_price - current_vwap) / current_vwap) * 100
                    pnl_pct = (pnl / entry_price) * 100

                    # ✅ STRICT EXECUTION: Exit at EXACTLY the threshold price (5% below VWAP)
                    # Not at current_price which could be 8%, 15%, 20% below VWAP
                    strict_exit_price = vwap_threshold
                    strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

                    self.log(f'📊 VWAP STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Current Price: ₹{current_price:.2f} ({vwap_diff_pct:.1f}% below VWAP), '
                            f'STRICT Exit: ₹{strict_exit_price:.2f} (exactly -5.0% below VWAP ₹{current_vwap:.2f}), '
                            f'STRICT P&L: {strict_pnl_pct:.1f}%')

                    # Store strict exit price for P&L calculation
                    pos_info['vwap_stop_triggered_price'] = strict_exit_price''',
        '''                    vwap_diff_pct = ((current_price - current_vwap) / current_vwap) * 100
                    pnl_pct = (pnl / entry_price) * 100
                    self.log(f'📊 VWAP STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Price: ₹{current_price:.2f}, VWAP: ₹{current_vwap:.2f} ({vwap_diff_pct:.1f}% below), P&L: {pnl_pct:.1f}%')
                    pos_info['vwap_stop_triggered_price'] = current_price'''
    )

    # Revert OI STOP
    content = content.replace(
        '''                    pnl_pct = (pnl / entry_price) * 100

                    # ✅ STRICT EXECUTION: Exit at price corresponding to EXACTLY 10% OI increase
                    # Use proportional calculation: if OI went from entry to current (e.g., +23.1%),
                    # and price dropped from entry to current, estimate price at exactly +10% OI
                    oi_threshold_pct = self.params.oi_increase_stop_pct * 100  # 10%
                    price_change = current_price - entry_price

                    # Calculate proportional price at exactly 10% OI increase
                    # If OI increased 23.1% and price dropped by X, at 10% OI increase price would have dropped by X * (10/23.1)
                    if oi_increase_pct > 0:
                        proportional_price_change = price_change * (oi_threshold_pct / oi_increase_pct)
                        strict_exit_price = entry_price + proportional_price_change
                    else:
                        strict_exit_price = current_price  # Fallback

                    strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

                    self.log(f'📈 OI INCREASE STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Entry OI: {pos_info["oi_at_entry"]:.0f}, Current OI: {current_oi:.0f} (+{oi_increase_pct:.1f}%), '
                            f'Current Price: ₹{current_price:.2f} (P&L: {pnl_pct:.1f}%), '
                            f'STRICT Exit: ₹{strict_exit_price:.2f} at exactly +{oi_threshold_pct:.0f}% OI (STRICT P&L: {strict_pnl_pct:.1f}%)')

                    # Store strict exit price for P&L calculation
                    pos_info['oi_stop_triggered_price'] = strict_exit_price''',
        '''                    pnl_pct = (pnl / entry_price) * 100
                    self.log(f'📈 OI INCREASE STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Entry OI: {pos_info["oi_at_entry"]:.0f}, Current OI: {current_oi:.0f} (+{oi_increase_pct:.1f}%), P&L: {pnl_pct:.1f}%')
                    pos_info['oi_stop_triggered_price'] = current_price'''
    )

    # Revert TRAILING STOP
    content = content.replace(
        '''            # Check trailing stop (for longs: exit if price drops back down)
            if current_price <= trailing_stop:
                # ✅ STRICT EXECUTION: Exit at EXACTLY the trailing stop price (10% below peak)
                strict_exit_price = trailing_stop
                strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

                self.log(f'📉 TRAILING STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Peak: ₹{pos_info["highest_price"]:.2f}, '
                        f'STRICT Exit: ₹{strict_exit_price:.2f} (exactly -10.0% from peak), '
                        f'STRICT P&L: {strict_pnl_pct:.1f}%')

                # Store strict exit price for accurate P&L calculation
                pos_info['trailing_stop_triggered_price'] = strict_exit_price''',
        '''            # Check trailing stop (for longs: exit if price drops back down)
            if current_price <= trailing_stop:
                self.log(f'📉 TRAILING STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{trailing_stop:.2f}')
                # Store the theoretical exit price for accurate P&L calculation
                pos_info['trailing_stop_triggered_price'] = current_price'''
    )

    # Write back to file
    with open(STRATEGY_FILE, 'w') as f:
        f.write(content)

    print("✅ Successfully reverted to NORMAL mode!")
    print("   All stops will now exit at CURRENT MARKET PRICE when thresholds are crossed.")
    return True


def enable_strict():
    """Enable STRICT execution mode"""
    print("Enabling STRICT execution mode...")

    with open(STRATEGY_FILE, 'r') as f:
        content = f.read()

    # Check if already in strict mode
    if 'STRICT EXECUTION' in content:
        print("❌ Already in STRICT mode. No changes needed.")
        return False

    # Enable INITIAL STOP LOSS (strict)
    content = content.replace(
        '''        # ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
        if current_price <= pos_info['stop_loss']:
            self.log(f'🛑 STOP LOSS HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, Stop: ₹{pos_info["stop_loss"]:.2f}')
            # Store the theoretical exit price (stop loss price) for accurate P&L calculation
            pos_info['stop_loss_triggered_price'] = current_price''',
        '''        # ALWAYS check initial stop loss first (for long positions, trigger when price goes DOWN)
        if current_price <= pos_info['stop_loss']:
            # ✅ STRICT EXECUTION: Exit at EXACTLY the 25% stop loss price
            strict_exit_price = pos_info['stop_loss']
            strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

            self.log(f'🛑 STOP LOSS HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                    f'Current: ₹{current_price:.2f}, STRICT Exit: ₹{strict_exit_price:.2f} (exactly -25.0% SL), '
                    f'STRICT P&L: {strict_pnl_pct:.1f}%')

            # Store strict exit price for accurate P&L calculation
            pos_info['stop_loss_triggered_price'] = strict_exit_price'''
    )

    # Enable VWAP STOP (strict)
    content = content.replace(
        '''                    vwap_diff_pct = ((current_price - current_vwap) / current_vwap) * 100
                    pnl_pct = (pnl / entry_price) * 100
                    self.log(f'📊 VWAP STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Price: ₹{current_price:.2f}, VWAP: ₹{current_vwap:.2f} ({vwap_diff_pct:.1f}% below), P&L: {pnl_pct:.1f}%')
                    pos_info['vwap_stop_triggered_price'] = current_price''',
        '''                    vwap_diff_pct = ((current_price - current_vwap) / current_vwap) * 100
                    pnl_pct = (pnl / entry_price) * 100

                    # ✅ STRICT EXECUTION: Exit at EXACTLY the threshold price (5% below VWAP)
                    # Not at current_price which could be 8%, 15%, 20% below VWAP
                    strict_exit_price = vwap_threshold
                    strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

                    self.log(f'📊 VWAP STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Current Price: ₹{current_price:.2f} ({vwap_diff_pct:.1f}% below VWAP), '
                            f'STRICT Exit: ₹{strict_exit_price:.2f} (exactly -5.0% below VWAP ₹{current_vwap:.2f}), '
                            f'STRICT P&L: {strict_pnl_pct:.1f}%')

                    # Store strict exit price for P&L calculation
                    pos_info['vwap_stop_triggered_price'] = strict_exit_price'''
    )

    # Enable OI STOP (strict)
    content = content.replace(
        '''                    pnl_pct = (pnl / entry_price) * 100
                    self.log(f'📈 OI INCREASE STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Entry OI: {pos_info["oi_at_entry"]:.0f}, Current OI: {current_oi:.0f} (+{oi_increase_pct:.1f}%), P&L: {pnl_pct:.1f}%')
                    pos_info['oi_stop_triggered_price'] = current_price''',
        '''                    pnl_pct = (pnl / entry_price) * 100

                    # ✅ STRICT EXECUTION: Exit at price corresponding to EXACTLY 10% OI increase
                    # Use proportional calculation: if OI went from entry to current (e.g., +23.1%),
                    # and price dropped from entry to current, estimate price at exactly +10% OI
                    oi_threshold_pct = self.params.oi_increase_stop_pct * 100  # 10%
                    price_change = current_price - entry_price

                    # Calculate proportional price at exactly 10% OI increase
                    # If OI increased 23.1% and price dropped by X, at 10% OI increase price would have dropped by X * (10/23.1)
                    if oi_increase_pct > 0:
                        proportional_price_change = price_change * (oi_threshold_pct / oi_increase_pct)
                        strict_exit_price = entry_price + proportional_price_change
                    else:
                        strict_exit_price = current_price  # Fallback

                    strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

                    self.log(f'📈 OI INCREASE STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                            f'Entry OI: {pos_info["oi_at_entry"]:.0f}, Current OI: {current_oi:.0f} (+{oi_increase_pct:.1f}%), '
                            f'Current Price: ₹{current_price:.2f} (P&L: {pnl_pct:.1f}%), '
                            f'STRICT Exit: ₹{strict_exit_price:.2f} at exactly +{oi_threshold_pct:.0f}% OI (STRICT P&L: {strict_pnl_pct:.1f}%)')

                    # Store strict exit price for P&L calculation
                    pos_info['oi_stop_triggered_price'] = strict_exit_price'''
    )

    # Enable TRAILING STOP (strict)
    content = content.replace(
        '''            # Check trailing stop (for longs: exit if price drops back down)
            if current_price <= trailing_stop:
                self.log(f'📉 TRAILING STOP HIT: {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Trailing Stop: ₹{trailing_stop:.2f}')
                # Store the theoretical exit price for accurate P&L calculation
                pos_info['trailing_stop_triggered_price'] = current_price''',
        '''            # Check trailing stop (for longs: exit if price drops back down)
            if current_price <= trailing_stop:
                # ✅ STRICT EXECUTION: Exit at EXACTLY the trailing stop price (10% below peak)
                strict_exit_price = trailing_stop
                strict_pnl_pct = ((strict_exit_price - entry_price) / entry_price) * 100

                self.log(f'📉 TRAILING STOP HIT (STRICT): {pos_info["option_type"]} {pos_info["strike"]} - '
                        f'Current: ₹{current_price:.2f}, Peak: ₹{pos_info["highest_price"]:.2f}, '
                        f'STRICT Exit: ₹{strict_exit_price:.2f} (exactly -10.0% from peak), '
                        f'STRICT P&L: {strict_pnl_pct:.1f}%')

                # Store strict exit price for accurate P&L calculation
                pos_info['trailing_stop_triggered_price'] = strict_exit_price'''
    )

    # Write back to file
    with open(STRATEGY_FILE, 'w') as f:
        f.write(content)

    print("✅ Successfully enabled STRICT mode!")
    print("   All stops will now exit at EXACT THRESHOLD PRICES (5%, 10%, 25%).")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Toggle between STRICT and NORMAL stop loss execution modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/toggle_strict_execution.py --mode strict   # Enable strict execution
  python scripts/toggle_strict_execution.py --mode normal   # Revert to normal
  python scripts/toggle_strict_execution.py --check         # Check current mode

What's the difference?
  STRICT:  Exits at EXACT threshold prices (5%, 10%, 25%) - Best for live trading
  NORMAL:  Exits at current market price when threshold crossed - Includes slippage
        """
    )

    parser.add_argument(
        '--mode',
        choices=['strict', 'normal'],
        help='Set execution mode: "strict" (exact thresholds) or "normal" (market price)'
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='Check current execution mode'
    )

    args = parser.parse_args()

    # Show usage if no arguments
    if not args.mode and not args.check:
        parser.print_help()
        sys.exit(0)

    # Check current mode
    if args.check:
        current_mode = check_current_mode()
        print(f"Current execution mode: {current_mode}")
        print()
        if current_mode == 'STRICT':
            print("  ✅ Stops exit at EXACT threshold prices (5%, 10%, 25%)")
            print("  ✅ Best for live trading with precise risk control")
        else:
            print("  ⚠️  Stops exit at CURRENT MARKET PRICE when thresholds crossed")
            print("  ⚠️  Includes slippage (3-4% average excess beyond thresholds)")
        sys.exit(0)

    # Toggle mode
    if args.mode == 'strict':
        enable_strict()
    elif args.mode == 'normal':
        revert_to_normal()

    # Show final status
    print()
    print("Current mode:", check_current_mode())
    print()
    print("Next steps:")
    print("  1. Run backtest: python backtest_runner.py")
    print("  2. Check logs for '(STRICT)' keywords in stop messages")
    print("  3. Verify trades.csv for exact threshold compliance")


if __name__ == '__main__':
    main()
