"""
Backtest Runner for Intraday Momentum OI Unwinding Strategy
Main entry point for running backtests
"""

import backtrader as bt
import pandas as pd
from datetime import datetime, time
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.config_loader import ConfigLoader
from src.data_loader import DataLoader
from src.oi_analyzer import OIAnalyzer
from src.reporter import Reporter
from strategies.intraday_momentum_oi import IntradayMomentumOI


class SpotPriceFeed(bt.feeds.PandasData):
    """Custom data feed for spot prices"""
    
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', -1),
    )


def run_backtest(config_path='config/strategy_config.yaml'):
    """
    Run backtest with given configuration
    
    Args:
        config_path: Path to configuration YAML file
    
    Returns:
        dict: Performance metrics
    """
    print("="*80)
    print(" " * 20 + "INTRADAY MOMENTUM OI UNWINDING STRATEGY")
    print(" " * 30 + "Backtest Runner")
    print("="*80 + "\n")
    
    # Load configuration
    print("Loading configuration...")
    config_loader = ConfigLoader(config_path)
    config = config_loader.load()
    print(f"Configuration loaded from: {config_path}\n")
    
    # Load and prepare data
    print("Preparing data...")
    data_loader = DataLoader(config)
    spot_df, options_df = data_loader.prepare_data()
    
    print(f"\nData Summary:")
    print(f"  Spot data: {len(spot_df)} bars from {spot_df.index[0]} to {spot_df.index[-1]}")
    print(f"  Options data: {len(options_df)} records")
    print(f"  Timeframe: {config['data']['timeframe']} minute(s)")
    print()
    
    # Initialize OI Analyzer
    print("Initializing OI Analyzer...")
    oi_analyzer = OIAnalyzer(options_df)
    
    # Initialize Backtrader
    print("Setting up Backtrader...")
    cerebro = bt.Cerebro()
    
    # Add data feed
    data_feed = SpotPriceFeed(dataname=spot_df)
    cerebro.adddata(data_feed)
    
    # Add strategy
    cerebro.addstrategy(
        IntradayMomentumOI,
        entry_start_time=time(*map(int, config['entry']['start_time'].split(':'))),
        entry_end_time=time(*map(int, config['entry']['end_time'].split(':'))),
        strikes_above_spot=config['entry']['strikes_above_spot'],
        strikes_below_spot=config['entry']['strikes_below_spot'],
        exit_start_time=time(*map(int, config['exit']['exit_start_time'].split(':'))),
        exit_end_time=time(*map(int, config['exit']['exit_end_time'].split(':'))),
        initial_stop_loss_pct=config['exit']['initial_stop_loss_pct'],
        profit_threshold=config['exit']['profit_threshold'],
        trailing_stop_pct=config['exit']['trailing_stop_pct'],
        vwap_stop_pct=config['exit']['vwap_stop_pct'],
        oi_increase_stop_pct=config['exit']['oi_increase_stop_pct'],
        position_size=config['position_sizing']['position_size'],
        max_positions=config['risk_management']['max_positions'],
        avoid_monday_tuesday=config['risk_management']['avoid_monday_tuesday'],
        lot_size=config['market']['option_lot_size'],
        options_df=options_df,
        oi_analyzer=oi_analyzer,
    )
    
    # Set broker parameters
    initial_capital = config['position_sizing']['initial_capital']
    cerebro.broker.setcash(initial_capital)

    # Set commission
    cerebro.broker.setcommission(commission=config['backtest']['commission'])
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    print(f"Initial Portfolio Value: ₹{cerebro.broker.getvalue():,.2f}\n")
    
    # Run backtest
    print("="*80)
    print("Running backtest...")
    print("="*80 + "\n")
    
    results = cerebro.run()
    strategy = results[0]
    
    print(f"\nFinal Portfolio Value: ₹{cerebro.broker.getvalue():,.2f}")
    
    # Generate reports
    reporter = Reporter(config)
    metrics = reporter.generate_full_report(cerebro, strategy)
    
    return metrics


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Intraday Momentum OI Unwinding backtest')
    parser.add_argument('--config', type=str, default='config/strategy_config.yaml',
                       help='Path to configuration file')
    
    args = parser.parse_args()
    
    try:
        metrics = run_backtest(args.config)
        print("\n✓ Backtest completed successfully!")
        return 0
    except Exception as e:
        print(f"\n✗ Error running backtest: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
