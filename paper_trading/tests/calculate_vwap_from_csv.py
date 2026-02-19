"""
Calculate VWAP from CSV using live trading calculation method
Uses incremental volume approach exactly as in live trading strategy
"""

import pandas as pd
import sys

def calculate_vwap_live_method(csv_path: str, output_path: str):
    """
    Calculate VWAP using the exact same logic as live trading:
    - Uses incremental volume (delta of cumulative volume)
    - Accumulates TPV (Typical Price * Volume) and volume
    - VWAP = Total TPV / Total Volume

    NOTE: If the CSV has individual candle volumes (not cumulative),
    they will be converted to cumulative first.

    Args:
        csv_path: Path to input CSV file
        output_path: Path to output CSV file with VWAP calculations
    """

    # Read the CSV
    print(f"Reading CSV from: {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"\nOriginal columns: {list(df.columns)}")
    print(f"Total rows: {len(df)}")
    print(f"\nFirst few rows:")
    print(df.head())

    # Detect if Volume is cumulative or individual
    # If volume decreases, it's individual candle volume, not cumulative
    is_cumulative = all(df['Volume'].iloc[i] <= df['Volume'].iloc[i+1]
                        for i in range(len(df)-1))

    if not is_cumulative:
        print("\n⚠️  Detected INDIVIDUAL candle volumes (not cumulative)")
        print("   Converting to cumulative volume for live trading method...")
        df['Candle_Volume'] = df['Volume'].copy()
        df['Volume'] = df['Candle_Volume'].cumsum()
        print(f"   Cumulative volume created: {df['Volume'].iloc[0]:,.0f} → {df['Volume'].iloc[-1]:,.0f}")
    else:
        print("\n✓ Detected CUMULATIVE volume")
        df['Candle_Volume'] = df['Volume'].diff().fillna(df['Volume'].iloc[0])

    # Initialize VWAP state (mimics vwap_state in live trading)
    vwap_state = {
        'tpv': 0.0,                     # Total Price * Volume
        'volume': 0.0,                  # Total incremental volume
        'prev_cumulative_volume': 0.0   # Track previous cumulative volume
    }

    # Lists to store calculated values
    vwap_values = []
    incremental_volumes = []
    tpv_added_list = []
    running_volumes = []

    print("\n" + "="*80)
    print("VWAP CALCULATION (Live Trading Method)")
    print("="*80)
    print(f"{'Row':<5} {'Time':<20} {'Close':>8} {'CandleVol':>12} {'CumulVol':>12} {'TPV_added':>14} {'RunVol':>12} {'VWAP':>10}")
    print("-"*80)

    for idx, row in df.iterrows():
        price = row['close']
        candle_volume = row['Candle_Volume']
        cumulative_volume = row['Volume']

        # Calculate incremental volume (same as live trading)
        prev_cumul = vwap_state['prev_cumulative_volume']
        incr_volume = cumulative_volume - prev_cumul

        # Calculate TPV added in this candle
        tpv_added = price * incr_volume

        # Update VWAP state
        vwap_state['tpv'] += tpv_added
        vwap_state['volume'] += incr_volume
        vwap_state['prev_cumulative_volume'] = cumulative_volume

        # Calculate VWAP
        total_vol = vwap_state['volume']
        if total_vol > 0:
            vwap = vwap_state['tpv'] / total_vol
        else:
            vwap = price

        # Store values
        vwap_values.append(vwap)
        incremental_volumes.append(incr_volume)
        tpv_added_list.append(tpv_added)
        running_volumes.append(total_vol)

        # Print detailed output for first 10 rows and every 10th row
        if idx < 10 or idx % 10 == 0:
            time_str = row['time'][:19] if len(row['time']) > 19 else row['time']
            print(f"{idx:<5} {time_str:<20} {price:>8.2f} {candle_volume:>12,.0f} {cumulative_volume:>12,.0f} "
                  f"{tpv_added:>14,.2f} {total_vol:>12,.0f} {vwap:>10.2f}")

    # Add calculated columns to dataframe
    # Reorder columns for better readability
    df['Cumulative_Volume'] = df['Volume']
    df['Incremental_Volume'] = incremental_volumes
    df['TPV_Added'] = tpv_added_list
    df['Running_Volume'] = running_volumes
    df['VWAP_Live_Calc'] = vwap_values

    # Calculate difference with TradingView VWAP (if exists)
    if 'VWAP-TV' in df.columns:
        df['VWAP_Difference'] = df['VWAP_Live_Calc'] - df['VWAP-TV']

    # Reorder columns for output
    column_order = ['time', 'open', 'high', 'low', 'close', 'Candle_Volume', 'Cumulative_Volume',
                    'Incremental_Volume', 'TPV_Added', 'Running_Volume', 'VWAP_Live_Calc']
    if 'VWAP-TV' in df.columns:
        column_order.extend(['VWAP-TV', 'VWAP_Difference'])

    # Keep only ordered columns (drop original Volume column)
    df = df[column_order]

    # Save to output file
    df.to_csv(output_path, index=False)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total candles processed: {len(df)}")
    print(f"Total incremental volume: {vwap_state['volume']:,.0f}")
    print(f"Total TPV: {vwap_state['tpv']:,.2f}")
    print(f"Final VWAP: {vwap_values[-1]:.4f}")

    if 'VWAP-TV' in df.columns:
        print(f"\nComparison with TradingView VWAP:")
        print(f"  TradingView final VWAP: {df['VWAP-TV'].iloc[-1]:.4f}")
        print(f"  Live calc final VWAP: {vwap_values[-1]:.4f}")
        print(f"  Difference: {vwap_values[-1] - df['VWAP-TV'].iloc[-1]:.4f}")

        avg_diff = df['VWAP_Difference'].mean()
        max_diff = df['VWAP_Difference'].abs().max()
        print(f"  Average difference: {avg_diff:.4f}")
        print(f"  Max absolute difference: {max_diff:.4f}")

    print(f"\nOutput saved to: {output_path}")
    print("\nOutput columns:")
    for col in df.columns:
        print(f"  - {col}")

    print("\n" + "="*80)
    print("Last 5 rows of output:")
    print("="*80)
    print(df.tail().to_string())

    return df


if __name__ == "__main__":
    # Input and output paths
    input_csv = '/Users/vidheeshetty/Downloads/NSE_NIFTY260217P25500.csv'
    output_csv = '/Users/vidheeshetty/Downloads/NSE_NIFTY260217P25500_VWAP_CALCULATED.csv'

    print("="*80)
    print("VWAP CALCULATOR - Live Trading Method")
    print("="*80)
    print(f"Input file: {input_csv}")
    print(f"Output file: {output_csv}")

    # Calculate VWAP
    result_df = calculate_vwap_live_method(input_csv, output_csv)

    print("\n✓ VWAP calculation complete!")
