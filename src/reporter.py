"""
Reporting Module
Generates performance reports and visualizations
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from datetime import datetime
import json


class Reporter:
    """Generate backtest reports and analytics"""
    
    def __init__(self, config):
        self.config = config
        self.output_dir = Path(config['reporting']['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def calculate_metrics(self, cerebro, strategy):
        """Calculate performance metrics"""
        metrics = {}
        
        # Get final portfolio value
        final_value = cerebro.broker.getvalue()
        initial_capital = self.config['position_sizing']['initial_capital']
        
        metrics['Initial Capital'] = initial_capital
        metrics['Final Value'] = final_value
        metrics['Total Return'] = final_value - initial_capital
        metrics['Total Return %'] = ((final_value / initial_capital) - 1) * 100
        
        # Get trade log from strategy
        if hasattr(strategy, 'trade_log') and len(strategy.trade_log) > 0:
            df_trades = pd.DataFrame(strategy.trade_log)
            
            metrics['Total Trades'] = len(df_trades)
            metrics['Winning Trades'] = len(df_trades[df_trades['pnl'] > 0])
            metrics['Losing Trades'] = len(df_trades[df_trades['pnl'] < 0])
            metrics['Win Rate %'] = (metrics['Winning Trades'] / metrics['Total Trades'] * 100) if metrics['Total Trades'] > 0 else 0
            
            metrics['Total PnL'] = df_trades['pnl'].sum()
            metrics['Average PnL'] = df_trades['pnl'].mean()
            metrics['Average PnL %'] = df_trades['pnl_pct'].mean()
            
            metrics['Best Trade'] = df_trades['pnl'].max()
            metrics['Worst Trade'] = df_trades['pnl'].min()
            
            # Profit factor
            gross_profit = df_trades[df_trades['pnl'] > 0]['pnl'].sum()
            gross_loss = abs(df_trades[df_trades['pnl'] < 0]['pnl'].sum())
            metrics['Profit Factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Calculate Sharpe Ratio (simplified)
            if len(df_trades) > 1:
                returns = df_trades['pnl_pct'] / 100
                sharpe = returns.mean() / returns.std() * (252 ** 0.5) if returns.std() > 0 else 0
                metrics['Sharpe Ratio'] = sharpe
            else:
                metrics['Sharpe Ratio'] = 0
            
            # Calculate Max Drawdown
            df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()
            df_trades['cumulative_max'] = df_trades['cumulative_pnl'].cummax()
            df_trades['drawdown'] = df_trades['cumulative_pnl'] - df_trades['cumulative_max']
            metrics['Max Drawdown'] = df_trades['drawdown'].min()
            metrics['Max Drawdown %'] = (metrics['Max Drawdown'] / initial_capital * 100)
        else:
            metrics['Total Trades'] = 0
            metrics['Win Rate %'] = 0
            metrics['Sharpe Ratio'] = 0
            metrics['Max Drawdown'] = 0
            metrics['Profit Factor'] = 0
        
        return metrics
    
    def save_metrics(self, metrics, filename='backtest_metrics.json'):
        """Save metrics to JSON file"""
        output_path = self.output_dir / filename
        
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        
        print(f"\nMetrics saved to: {output_path}")
        return output_path
    
    def save_trades(self, strategy, filename='trades.csv'):
        """Save trade log to CSV"""
        if hasattr(strategy, 'trade_log') and len(strategy.trade_log) > 0:
            df_trades = pd.DataFrame(strategy.trade_log)
            output_path = self.output_dir / filename
            df_trades.to_csv(output_path, index=False)
            print(f"Trades saved to: {output_path}")
            return output_path
        else:
            print("No trades to save")
            return None
    
    def print_metrics(self, metrics):
        """Print metrics to console"""
        print("\n" + "="*80)
        print(" " * 30 + "BACKTEST RESULTS")
        print("="*80)
        
        print(f"\nCapital:")
        print(f"  Initial Capital:        ₹{metrics['Initial Capital']:,.2f}")
        print(f"  Final Value:            ₹{metrics['Final Value']:,.2f}")
        print(f"  Total Return:           ₹{metrics['Total Return']:,.2f}")
        print(f"  Total Return %:         {metrics['Total Return %']:.2f}%")
        
        print(f"\nTrade Statistics:")
        print(f"  Total Trades:           {metrics['Total Trades']}")
        
        if metrics['Total Trades'] > 0:
            print(f"  Winning Trades:         {metrics['Winning Trades']}")
            print(f"  Losing Trades:          {metrics['Losing Trades']}")
            print(f"  Win Rate:               {metrics['Win Rate %']:.2f}%")
            print(f"\nProfitability:")
            print(f"  Total PnL:              ₹{metrics['Total PnL']:,.2f}")
            print(f"  Average PnL:            ₹{metrics['Average PnL']:,.2f}")
            print(f"  Average PnL %:          {metrics['Average PnL %']:.2f}%")
            print(f"  Best Trade:             ₹{metrics['Best Trade']:,.2f}")
            print(f"  Worst Trade:            ₹{metrics['Worst Trade']:,.2f}")
            print(f"  Profit Factor:          {metrics['Profit Factor']:.2f}")
            
            print(f"\nRisk Metrics:")
            print(f"  Sharpe Ratio:           {metrics['Sharpe Ratio']:.2f}")
            print(f"  Max Drawdown:           ₹{metrics['Max Drawdown']:,.2f}")
            print(f"  Max Drawdown %:         {metrics['Max Drawdown %']:.2f}%")
        
        print("="*80 + "\n")
    
    def plot_equity_curve(self, strategy, filename='equity_curve.png'):
        """Plot equity curve"""
        if not hasattr(strategy, 'trade_log') or len(strategy.trade_log) == 0:
            print("No trades to plot")
            return None
        
        df_trades = pd.DataFrame(strategy.trade_log)
        initial_capital = self.config['position_sizing']['initial_capital']
        
        df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()
        df_trades['portfolio_value'] = initial_capital + df_trades['cumulative_pnl']
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # Plot 1: Equity Curve
        ax1.plot(df_trades['exit_time'], df_trades['portfolio_value'], 
                linewidth=2, label='Portfolio Value')
        ax1.axhline(y=initial_capital, color='r', linestyle='--', 
                   linewidth=1, label='Initial Capital')
        ax1.set_xlabel('Date', fontsize=12)
        ax1.set_ylabel('Portfolio Value (₹)', fontsize=12)
        ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Plot 2: Drawdown
        df_trades['cumulative_max'] = df_trades['portfolio_value'].cummax()
        df_trades['drawdown'] = ((df_trades['portfolio_value'] - df_trades['cumulative_max']) 
                                 / df_trades['cumulative_max'] * 100)
        
        ax2.fill_between(df_trades['exit_time'], df_trades['drawdown'], 0, 
                        color='red', alpha=0.3)
        ax2.plot(df_trades['exit_time'], df_trades['drawdown'], 
                color='darkred', linewidth=1)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Drawdown (%)', fontsize=12)
        ax2.set_title('Drawdown', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Save plot
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Equity curve saved to: {output_path}")
        return output_path
    
    def plot_trade_analysis(self, strategy, filename='trade_analysis.png'):
        """Plot trade analysis"""
        if not hasattr(strategy, 'trade_log') or len(strategy.trade_log) == 0:
            print("No trades to plot")
            return None
        
        df_trades = pd.DataFrame(strategy.trade_log)
        
        # Create figure
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # Plot 1: PnL Distribution
        ax1 = axes[0, 0]
        colors = ['green' if x > 0 else 'red' for x in df_trades['pnl']]
        ax1.bar(range(len(df_trades)), df_trades['pnl'], color=colors, alpha=0.6)
        ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax1.set_xlabel('Trade Number', fontsize=10)
        ax1.set_ylabel('PnL (₹)', fontsize=10)
        ax1.set_title('Trade PnL Distribution', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: PnL Histogram
        ax2 = axes[0, 1]
        ax2.hist(df_trades['pnl'], bins=30, color='steelblue', alpha=0.7, edgecolor='black')
        ax2.axvline(x=0, color='red', linestyle='--', linewidth=1)
        ax2.set_xlabel('PnL (₹)', fontsize=10)
        ax2.set_ylabel('Frequency', fontsize=10)
        ax2.set_title('PnL Histogram', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Cumulative PnL
        ax3 = axes[1, 0]
        df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()
        ax3.plot(range(len(df_trades)), df_trades['cumulative_pnl'], 
                linewidth=2, color='blue')
        ax3.axhline(y=0, color='red', linestyle='--', linewidth=1)
        ax3.set_xlabel('Trade Number', fontsize=10)
        ax3.set_ylabel('Cumulative PnL (₹)', fontsize=10)
        ax3.set_title('Cumulative PnL', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        
        # Plot 4: Win/Loss Ratio
        ax4 = axes[1, 1]
        wins = len(df_trades[df_trades['pnl'] > 0])
        losses = len(df_trades[df_trades['pnl'] < 0])
        ax4.pie([wins, losses], labels=['Wins', 'Losses'], 
               colors=['green', 'red'], autopct='%1.1f%%', startangle=90)
        ax4.set_title(f'Win Rate: {wins/(wins+losses)*100:.1f}%', 
                     fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        
        # Save plot
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Trade analysis saved to: {output_path}")
        return output_path
    
    def generate_full_report(self, cerebro, strategy):
        """Generate complete report with all metrics and plots"""
        print("\nGenerating backtest report...")
        
        # Calculate metrics
        metrics = self.calculate_metrics(cerebro, strategy)
        
        # Print metrics
        self.print_metrics(metrics)
        
        # Save metrics
        self.save_metrics(metrics)
        
        # Save trades
        if self.config['reporting']['save_trades']:
            self.save_trades(strategy)
        
        # Generate plots
        if self.config['reporting']['generate_plots']:
            self.plot_equity_curve(strategy)
            self.plot_trade_analysis(strategy)
        
        print(f"\nAll reports saved to: {self.output_dir}")
        
        return metrics

