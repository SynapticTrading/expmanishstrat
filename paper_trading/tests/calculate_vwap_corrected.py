"""
VWAP Calculation - Corrected vs Current Live Trading Behavior

This script demonstrates:
1. CORRECT METHOD: Proper VWAP using historical bars (each bar's actual price × volume)
2. CURRENT LIVE TRADING: Buggy initialization (current price × cumulative volume)

The live trading bug: When initializing VWAP, it uses current price with total
cumulative volume, instead of accumulating each bar's (price × volume).
"""

import pandas as pd
import sys

def calculate_proper_vwap(csv_path: str, output_path: str):
    """
    Calculate VWAP using BOTH methods for comparison:
    - Method 1: CORRECT - Using historical bars (proper initialization)
    - Method 2: LIVE TRADING BUG - Using current price × cumulative volume
    """

    # Read the CSV
    print(f"Reading CSV from: {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"\nOriginal columns: {list(df.columns)}")
    print(f"Total rows: {len(df)}")

    # Detect if Volume is cumulative or individual
    is_cumulative = all(df['Volume'].iloc[i] <= df['Volume'].iloc[i+1]
                        for i in range(len(df)-1))

    if not is_cumulative:
        print("\n⚠️  Detected INDIVIDUAL candle volumes (not cumulative)")
        print("   Converting to cumulative volume...")
        df['Candle_Volume'] = df['Volume'].copy()
        df['Volume_Cumulative'] = df['Candle_Volume'].cumsum()
    else:
        print("\n✓ Detected CUMULATIVE volume")
        df['Volume_Cumulative'] = df['Volume'].copy()
        df['Candle_Volume'] = df['Volume'].diff().fillna(df['Volume'].iloc[0])

    # ═══════════════════════════════════════════════════════════════════════════
    # METHOD 1: CORRECT VWAP - Using historical bars
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*80)
    print("METHOD 1: CORRECT VWAP (Historical Bars)")
    print("="*80)
    print("Each bar contributes: (bar's close × bar's volume) to total TPV")
    print()

    vwap_correct_state = {
        'tpv': 0.0,
        'volume': 0.0,
        'prev_cumulative_volume': 0.0
    }

    vwap_correct_values = []

    print(f"{'Row':<5} {'Time':<20} {'Close':>8} {'CandleVol':>12} {'TPV_added':>14} {'Total_TPV':>14} {'Total_Vol':>12} {'VWAP':>10}")
    print("-"*80)

    for idx, row in df.iterrows():
        price = row['close']
        candle_volume = row['Candle_Volume']
        cumulative_volume = row['Volume_Cumulative']

        # Calculate incremental volume
        prev_cumul = vwap_correct_state['prev_cumulative_volume']
        incr_volume = cumulative_volume - prev_cumul

        # CORRECT: Use this bar's actual price × this bar's actual volume
        tpv_added = price * incr_volume

        # Update running totals
        vwap_correct_state['tpv'] += tpv_added
        vwap_correct_state['volume'] += incr_volume
        vwap_correct_state['prev_cumulative_volume'] = cumulative_volume

        # Calculate VWAP
        total_vol = vwap_correct_state['volume']
        if total_vol > 0:
            vwap = vwap_correct_state['tpv'] / total_vol
        else:
            vwap = price

        vwap_correct_values.append(vwap)

        # Print details for key rows
        if idx < 5 or idx == 23:  # First 5 and last row
            time_str = row['time'][:19] if len(row['time']) > 19 else row['time']
            print(f"{idx:<5} {time_str:<20} {price:>8.2f} {candle_volume:>12,.0f} "
                  f"{tpv_added:>14,.2f} {vwap_correct_state['tpv']:>14,.2f} "
                  f"{total_vol:>12,.0f} {vwap:>10.2f}")

    df['VWAP_Correct'] = vwap_correct_values

    # ═══════════════════════════════════════════════════════════════════════════
    # METHOD 2: LIVE TRADING BUG - Simulating incorrect initialization
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*80)
    print("METHOD 2: CURRENT LIVE TRADING BEHAVIOR (Bug Simulation)")
    print("="*80)
    print("Simulates what happens when initializing at row 3 (09:30:00)")
    print("Bug: Uses current price (71.60) × total cumulative volume (49.6M)")
    print()

    # Simulate initialization at row 3 (index 3, which is 09:30:00)
    init_row_idx = 3
    init_row = df.iloc[init_row_idx]

    print(f"Initialization at row {init_row_idx} ({init_row['time']}):")
    print(f"  Current price: {init_row['close']:.2f}")
    print(f"  Cumulative volume: {init_row['Volume_Cumulative']:,.0f}")
    print(f"  Bug: TPV = {init_row['close']:.2f} × {init_row['Volume_Cumulative']:,.0f} = {init_row['close'] * init_row['Volume_Cumulative']:,.2f}")
    print(f"  Bug: VWAP = TPV / Volume = {init_row['close']:.2f} (same as price!)")
    print()

    # Calculate what SHOULD have been if properly initialized with historical data
    correct_tpv_at_init = df.iloc[:init_row_idx+1].apply(
        lambda row: row['close'] * row['Candle_Volume'], axis=1
    ).sum()
    correct_vol_at_init = df.iloc[:init_row_idx+1]['Candle_Volume'].sum()
    correct_vwap_at_init = correct_tpv_at_init / correct_vol_at_init

    print(f"What SHOULD have been (correct historical initialization):")
    print(f"  Bar 0 (09:15): 57.20 × 18,623,215 = {57.20 * 18623215:,.2f}")
    print(f"  Bar 1 (09:20): 54.90 × 10,821,395 = {54.90 * 10821395:,.2f}")
    print(f"  Bar 2 (09:25): 59.35 × 5,887,830 = {59.35 * 5887830:,.2f}")
    print(f"  Bar 3 (09:30): 71.60 × 14,286,090 = {71.60 * 14286090:,.2f}")
    print(f"  Total TPV: {correct_tpv_at_init:,.2f}")
    print(f"  Total Volume: {correct_vol_at_init:,.0f}")
    print(f"  CORRECT VWAP: {correct_vwap_at_init:.2f}")
    print()
    print(f"Difference: {init_row['close'] - correct_vwap_at_init:.2f} (Live shows {init_row['close']:.2f} vs Correct {correct_vwap_at_init:.2f})")

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPARISON SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    print("\n" + "="*80)
    print("COMPARISON: TradingView vs Correct vs Live Trading Bug")
    print("="*80)

    # Create comparison DataFrame
    comparison = df[['time', 'close', 'Candle_Volume', 'Volume_Cumulative']].copy()
    comparison['VWAP_Correct'] = df['VWAP_Correct']
    if 'VWAP-TV' in df.columns:
        comparison['VWAP_TradingView'] = df['VWAP-TV']
        comparison['Diff_TV_vs_Correct'] = df['VWAP-TV'] - df['VWAP_Correct']

    # Show key rows
    print("\nKey timestamps:")
    print(comparison.iloc[[0, 1, 2, 3, 4, -1]].to_string())

    # At row 3 (09:30:00) - where live trading initialized
    print(f"\n" + "="*80)
    print(f"AT ROW 3 (09:30:00) - When Live Trading Initialized VWAP:")
    print("="*80)
    print(f"Close Price:              {df.iloc[3]['close']:.2f}")
    print(f"VWAP (Correct Method):    {df.iloc[3]['VWAP_Correct']:.2f}")
    if 'VWAP-TV' in df.columns:
        print(f"VWAP (TradingView):       {df.iloc[3]['VWAP-TV']:.2f}")
    print(f"VWAP (Live Trading Bug):  {df.iloc[3]['close']:.2f}  ← Same as price!")
    print()
    print(f"Error in live trading: {abs(df.iloc[3]['close'] - df.iloc[3]['VWAP_Correct']):.2f} points")

    # Save output
    output_columns = ['time', 'open', 'high', 'low', 'close',
                      'Candle_Volume', 'Volume_Cumulative', 'VWAP_Correct']
    if 'VWAP-TV' in df.columns:
        output_columns.append('VWAP-TV')
    if 'Diff_TV_vs_Correct' in comparison.columns:
        df['Diff_TV_vs_Correct'] = comparison['Diff_TV_vs_Correct']
        output_columns.append('Diff_TV_vs_Correct')

    df[output_columns].to_csv(output_path, index=False)

    print(f"\n✓ Output saved to: {output_path}")
    print(f"\nColumns in output:")
    for col in output_columns:
        print(f"  - {col}")

    return df


if __name__ == "__main__":
    input_csv = '/Users/vidheeshetty/Downloads/NSE_NIFTY260217P25500.csv'
    output_csv = '/Users/vidheeshetty/Downloads/NSE_NIFTY260217P25500_VWAP_CORRECTED.csv'

    print("="*80)
    print("VWAP CALCULATOR - CORRECT vs LIVE TRADING BUG")
    print("="*80)
    print(f"Input:  {input_csv}")
    print(f"Output: {output_csv}")

    result_df = calculate_proper_vwap(input_csv, output_csv)

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    print("The live trading system has a bug when initializing VWAP:")
    print("  ✗ Current: Uses current_price × cumulative_volume")
    print("  ✓ Correct: Should accumulate (each_bar_price × each_bar_volume)")
    print()
    print("To fix: The live trading code should backfill VWAP with historical")
    print("        candle data when a new strike is selected, not just use the")
    print("        current price with total cumulative volume.")
    print("="*80)
