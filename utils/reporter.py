"""
Reporting Module
Generates comprehensive backtest reports and analytics
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class BacktestReporter:
    """Generate comprehensive backtest reports"""

    def __init__(self, config, output_dir: str = 'reports'):
        """
        Initialize reporter

        Args:
            config: Configuration instance
            output_dir: Directory to save reports
        """
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        trades: List[Dict],
        initial_capital: float,
        strategy_name: str = 'Intraday_Momentum_OI'
    ):
        """
        Generate comprehensive backtest report

        Args:
            trades: List of trade dictionaries
            initial_capital: Starting capital
            strategy_name: Name of strategy
        """
        if not trades:
            logger.warning("No trades to report")
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Convert trades to DataFrame
        trades_df = pd.DataFrame(trades)

        # Generate various reports
        summary_stats = self._calculate_summary_statistics(trades_df, initial_capital)
        monthly_stats = self._calculate_monthly_statistics(trades_df)
        trade_analysis = self._analyze_trades(trades_df)

        # Save reports
        self._save_trades_csv(trades_df, timestamp)
        self._save_summary_json(summary_stats, timestamp)
        self._save_monthly_csv(monthly_stats, timestamp)
        self._save_html_report(
            trades_df, summary_stats, monthly_stats, trade_analysis, timestamp
        )

        # Print summary to console
        self._print_summary(summary_stats)

        logger.info(f"Reports saved to {self.output_dir}")

    def _calculate_summary_statistics(
        self,
        trades_df: pd.DataFrame,
        initial_capital: float
    ) -> Dict:
        """Calculate summary statistics"""
        total_trades = len(trades_df)

        if total_trades == 0:
            return {}

        # P&L metrics
        total_pnl = trades_df['pnl'].sum()
        total_pnl_pct = (total_pnl / initial_capital) * 100

        # Win/Loss metrics
        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] <= 0]

        num_wins = len(winning_trades)
        num_losses = len(losing_trades)
        win_rate = (num_wins / total_trades) * 100 if total_trades > 0 else 0

        avg_win = winning_trades['pnl'].mean() if num_wins > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if num_losses > 0 else 0
        avg_win_pct = winning_trades['pnl_pct'].mean() if num_wins > 0 else 0
        avg_loss_pct = losing_trades['pnl_pct'].mean() if num_losses > 0 else 0

        # Profit factor
        gross_profit = winning_trades['pnl'].sum() if num_wins > 0 else 0
        gross_loss = abs(losing_trades['pnl'].sum()) if num_losses > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

        # Max metrics
        max_win = trades_df['pnl'].max()
        max_loss = trades_df['pnl'].min()
        max_win_pct = trades_df['pnl_pct'].max()
        max_loss_pct = trades_df['pnl_pct'].min()

        # Consecutive wins/losses
        trades_df['win'] = trades_df['pnl'] > 0
        trades_df['streak'] = (trades_df['win'] != trades_df['win'].shift()).cumsum()
        win_streaks = trades_df[trades_df['win']].groupby('streak').size()
        loss_streaks = trades_df[~trades_df['win']].groupby('streak').size()

        max_consecutive_wins = win_streaks.max() if len(win_streaks) > 0 else 0
        max_consecutive_losses = loss_streaks.max() if len(loss_streaks) > 0 else 0

        # Drawdown
        trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
        trades_df['cumulative_return'] = (
            (initial_capital + trades_df['cumulative_pnl']) / initial_capital - 1
        ) * 100
        trades_df['running_max'] = trades_df['cumulative_pnl'].cummax()
        trades_df['drawdown'] = trades_df['cumulative_pnl'] - trades_df['running_max']
        max_drawdown = trades_df['drawdown'].min()
        max_drawdown_pct = (max_drawdown / initial_capital) * 100

        # Time metrics
        trades_df['trade_duration'] = (
            pd.to_datetime(trades_df['exit_time']) -
            pd.to_datetime(trades_df['entry_time'])
        )
        avg_trade_duration = trades_df['trade_duration'].mean()

        # Risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(trades_df['pnl'])

        summary = {
            'initial_capital': initial_capital,
            'final_capital': initial_capital + total_pnl,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'total_trades': total_trades,
            'winning_trades': num_wins,
            'losing_trades': num_losses,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'profit_factor': profit_factor,
            'max_win': max_win,
            'max_loss': max_loss,
            'max_win_pct': max_win_pct,
            'max_loss_pct': max_loss_pct,
            'max_consecutive_wins': int(max_consecutive_wins),
            'max_consecutive_losses': int(max_consecutive_losses),
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_trade_duration': str(avg_trade_duration),
            'sharpe_ratio': sharpe_ratio,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss
        }

        return summary

    def _calculate_monthly_statistics(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate monthly statistics"""
        trades_df['month'] = pd.to_datetime(trades_df['entry_time']).dt.to_period('M')

        monthly = trades_df.groupby('month').agg({
            'pnl': ['sum', 'count'],
            'pnl_pct': 'mean'
        }).reset_index()

        monthly.columns = ['month', 'total_pnl', 'num_trades', 'avg_pnl_pct']

        # Calculate win rate per month
        monthly_wins = trades_df[trades_df['pnl'] > 0].groupby('month').size()
        monthly['win_rate'] = (monthly_wins / monthly['num_trades'] * 100).fillna(0)

        return monthly

    def _analyze_trades(self, trades_df: pd.DataFrame) -> Dict:
        """Analyze trade patterns"""
        analysis = {}

        # By option type
        type_analysis = trades_df.groupby('option_type').agg({
            'pnl': ['sum', 'mean', 'count']
        })
        analysis['by_option_type'] = type_analysis.to_dict()

        # By exit reason
        reason_analysis = trades_df.groupby('exit_reason').agg({
            'pnl': ['sum', 'mean', 'count']
        })
        analysis['by_exit_reason'] = reason_analysis.to_dict()

        return analysis

    def _calculate_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float = 0.05) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0

        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe = excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0

        # Annualize (assuming ~252 trading days)
        sharpe_annual = sharpe * np.sqrt(252)

        return sharpe_annual

    def _save_trades_csv(self, trades_df: pd.DataFrame, timestamp: str):
        """Save trades to CSV"""
        filepath = self.output_dir / f'trades_{timestamp}.csv'
        trades_df.to_csv(filepath, index=False)
        logger.info(f"Trades saved to {filepath}")

    def _save_summary_json(self, summary: Dict, timestamp: str):
        """Save summary statistics to JSON"""
        filepath = self.output_dir / f'summary_{timestamp}.json'

        # Convert numpy types to Python types for JSON serialization
        summary_clean = {}
        for key, value in summary.items():
            if isinstance(value, (np.integer, np.floating)):
                summary_clean[key] = float(value)
            else:
                summary_clean[key] = value

        with open(filepath, 'w') as f:
            json.dump(summary_clean, f, indent=4)

        logger.info(f"Summary saved to {filepath}")

    def _save_monthly_csv(self, monthly_df: pd.DataFrame, timestamp: str):
        """Save monthly statistics to CSV"""
        filepath = self.output_dir / f'monthly_{timestamp}.csv'
        monthly_df.to_csv(filepath, index=False)
        logger.info(f"Monthly stats saved to {filepath}")

    def _save_html_report(
        self,
        trades_df: pd.DataFrame,
        summary: Dict,
        monthly: pd.DataFrame,
        analysis: Dict,
        timestamp: str
    ):
        """Generate and save HTML report"""
        html_content = self._generate_html(trades_df, summary, monthly, analysis)

        filepath = self.output_dir / f'report_{timestamp}.html'
        with open(filepath, 'w') as f:
            f.write(html_content)

        logger.info(f"HTML report saved to {filepath}")

    def _generate_html(
        self,
        trades_df: pd.DataFrame,
        summary: Dict,
        monthly: pd.DataFrame,
        analysis: Dict
    ) -> str:
        """Generate HTML report content"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report - Intraday Momentum OI Strategy</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; border-bottom: 2px solid #ddd; padding-bottom: 5px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; background-color: #e3f2fd; border-radius: 5px; min-width: 200px; }}
        .metric-label {{ font-weight: bold; color: #555; }}
        .metric-value {{ font-size: 24px; color: #1976d2; }}
        .positive {{ color: green; }}
        .negative {{ color: red; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Backtest Report: Intraday Momentum OI Strategy</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>Summary Statistics</h2>
        <div class="metric">
            <div class="metric-label">Initial Capital</div>
            <div class="metric-value">₹{summary['initial_capital']:,.2f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Final Capital</div>
            <div class="metric-value">₹{summary['final_capital']:,.2f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Total P&L</div>
            <div class="metric-value {'positive' if summary['total_pnl'] > 0 else 'negative'}">
                ₹{summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.2f}%)
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Total Trades</div>
            <div class="metric-value">{summary['total_trades']}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value">{summary['win_rate']:.2f}%</div>
        </div>
        <div class="metric">
            <div class="metric-label">Profit Factor</div>
            <div class="metric-value">{summary['profit_factor']:.2f}</div>
        </div>

        <h2>Performance Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Winning Trades</td>
                <td>{summary['winning_trades']} ({summary['win_rate']:.2f}%)</td>
            </tr>
            <tr>
                <td>Losing Trades</td>
                <td>{summary['losing_trades']}</td>
            </tr>
            <tr>
                <td>Average Win</td>
                <td>₹{summary['avg_win']:,.2f} ({summary['avg_win_pct']:.2f}%)</td>
            </tr>
            <tr>
                <td>Average Loss</td>
                <td>₹{summary['avg_loss']:,.2f} ({summary['avg_loss_pct']:.2f}%)</td>
            </tr>
            <tr>
                <td>Max Win</td>
                <td>₹{summary['max_win']:,.2f} ({summary['max_win_pct']:.2f}%)</td>
            </tr>
            <tr>
                <td>Max Loss</td>
                <td>₹{summary['max_loss']:,.2f} ({summary['max_loss_pct']:.2f}%)</td>
            </tr>
            <tr>
                <td>Max Consecutive Wins</td>
                <td>{summary['max_consecutive_wins']}</td>
            </tr>
            <tr>
                <td>Max Consecutive Losses</td>
                <td>{summary['max_consecutive_losses']}</td>
            </tr>
            <tr>
                <td>Max Drawdown</td>
                <td>₹{summary['max_drawdown']:,.2f} ({summary['max_drawdown_pct']:.2f}%)</td>
            </tr>
            <tr>
                <td>Sharpe Ratio</td>
                <td>{summary['sharpe_ratio']:.2f}</td>
            </tr>
            <tr>
                <td>Gross Profit</td>
                <td>₹{summary['gross_profit']:,.2f}</td>
            </tr>
            <tr>
                <td>Gross Loss</td>
                <td>₹{summary['gross_loss']:,.2f}</td>
            </tr>
        </table>

        <h2>Monthly Performance</h2>
        <table>
            <tr>
                <th>Month</th>
                <th>Total P&L</th>
                <th>Trades</th>
                <th>Avg P&L %</th>
                <th>Win Rate</th>
            </tr>
            {''.join([f"<tr><td>{row['month']}</td><td>₹{row['total_pnl']:,.2f}</td><td>{row['num_trades']}</td><td>{row['avg_pnl_pct']:.2f}%</td><td>{row['win_rate']:.2f}%</td></tr>" for _, row in monthly.iterrows()])}
        </table>

        <h2>Recent Trades</h2>
        <table>
            <tr>
                <th>Entry Time</th>
                <th>Exit Time</th>
                <th>Type</th>
                <th>Strike</th>
                <th>Entry Price</th>
                <th>Exit Price</th>
                <th>P&L</th>
                <th>P&L %</th>
                <th>Exit Reason</th>
            </tr>
            {''.join([f"<tr><td>{row['entry_time']}</td><td>{row['exit_time']}</td><td>{row['option_type']}</td><td>{row['strike']}</td><td>₹{row['entry_price']:.2f}</td><td>₹{row['exit_price']:.2f}</td><td class=\"{'positive' if row['pnl'] > 0 else 'negative'}\">₹{row['pnl']:,.2f}</td><td class=\"{'positive' if row['pnl_pct'] > 0 else 'negative'}\">{row['pnl_pct']:.2f}%</td><td>{row['exit_reason']}</td></tr>" for _, row in trades_df.tail(20).iterrows()])}
        </table>
    </div>
</body>
</html>
        """

        return html

    def _print_summary(self, summary: Dict):
        """Print summary to console"""
        print("\n" + "="*80)
        print("BACKTEST SUMMARY")
        print("="*80)
        print(f"Initial Capital:       ₹{summary['initial_capital']:,.2f}")
        print(f"Final Capital:         ₹{summary['final_capital']:,.2f}")
        print(f"Total P&L:             ₹{summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.2f}%)")
        print(f"Total Trades:          {summary['total_trades']}")
        print(f"Win Rate:              {summary['win_rate']:.2f}%")
        print(f"Profit Factor:         {summary['profit_factor']:.2f}")
        print(f"Max Drawdown:          ₹{summary['max_drawdown']:,.2f} ({summary['max_drawdown_pct']:.2f}%)")
        print(f"Sharpe Ratio:          {summary['sharpe_ratio']:.2f}")
        print("="*80 + "\n")
