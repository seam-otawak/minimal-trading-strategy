#!/usr/bin/env python3
"""
📊 Backtesting Engine for Smart Buy-Hold Strategy
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import ccxt
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BuyHoldBacktester:
    """Backtesting engine for buy-hold strategy"""
    
    def __init__(self, config_path: str = 'config.json'):
        """Initialize backtester"""
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    
    def fetch_historical_data(self, symbol: str, days: int) -> pd.DataFrame:
        """Fetch historical OHLCV data"""
        try:
            since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            ohlcv = self.exchange.fetch_ohlcv(symbol, '1d', since=since, limit=days)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return pd.DataFrame()
    
    def calculate_buy_hold_return(self, df: pd.DataFrame) -> float:
        """Calculate simple buy-and-hold return"""
        if len(df) < 2:
            return 0.0
        
        start_price = df['close'].iloc[0]
        end_price = df['close'].iloc[-1]
        
        return (end_price - start_price) / start_price
    
    def calculate_metrics(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance metrics"""
        returns = df['close'].pct_change().dropna()
        
        # Total return
        total_return = self.calculate_buy_hold_return(df)
        
        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(365)
        
        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe = (returns.mean() * 365) / volatility if volatility > 0 else 0
        
        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        return {
            'total_return': total_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown
        }
    
    def run_backtest(self, pairs: List[str], days: int) -> Dict[str, Dict[str, float]]:
        """Run backtest on multiple pairs"""
        results = {}
        
        for pair in pairs:
            logger.info(f"Backtesting {pair}...")
            
            # Fetch data
            df = self.fetch_historical_data(pair, days)
            
            if not df.empty:
                # Calculate metrics
                metrics = self.calculate_metrics(df)
                results[pair] = metrics
                
                logger.info(f"{pair}: {metrics['total_return']:.2%} return, "
                          f"{metrics['sharpe_ratio']:.2f} Sharpe")
            else:
                logger.warning(f"No data for {pair}")
        
        return results
    
    def generate_report(self, results: Dict[str, Dict[str, float]], days: int) -> str:
        """Generate backtest report"""
        report = f"""# 📊 Buy-Hold Backtest Report

## Test Parameters
- **Period**: {days} days
- **Strategy**: Simple Buy-and-Hold
- **Pairs**: {len(results)} tested

## Results Summary

| Pair | Return | Volatility | Sharpe | Max Drawdown |
|------|--------|------------|--------|--------------|
"""
        
        total_return = 0
        for pair, metrics in sorted(results.items(), key=lambda x: x[1]['total_return'], reverse=True):
            report += f"| {pair} | {metrics['total_return']:.2%} | "
            report += f"{metrics['volatility']:.2%} | {metrics['sharpe_ratio']:.2f} | "
            report += f"{metrics['max_drawdown']:.2%} |\n"
            total_return += metrics['total_return']
        
        avg_return = total_return / len(results) if results else 0
        
        report += f"\n**Average Return**: {avg_return:.2%}\n"
        
        # Add insights
        report += "\n## Key Insights\n\n"
        
        # Best performer
        if results:
            best_pair = max(results.items(), key=lambda x: x[1]['total_return'])
            worst_pair = min(results.items(), key=lambda x: x[1]['total_return'])
            
            report += f"- **Best Performer**: {best_pair[0]} ({best_pair[1]['total_return']:.2%})\n"
            report += f"- **Worst Performer**: {worst_pair[0]} ({worst_pair[1]['total_return']:.2%})\n"
            
            # Risk analysis
            avg_sharpe = sum(m['sharpe_ratio'] for m in results.values()) / len(results)
            report += f"- **Average Sharpe Ratio**: {avg_sharpe:.2f}\n"
            
            # Market condition
            if avg_return > 0.1:
                report += "- **Market Condition**: Strong Bull Market\n"
            elif avg_return > 0:
                report += "- **Market Condition**: Mild Bull Market\n"
            else:
                report += "- **Market Condition**: Bear Market\n"
        
        return report
    
    def save_results(self, results: Dict[str, Dict[str, float]], days: int):
        """Save backtest results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save raw results
        results_file = f'backtest_results_{timestamp}.json'
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'days': days,
                'results': results
            }, f, indent=2)
        
        logger.info(f"💾 Results saved to {results_file}")
        
        # Save report
        report = self.generate_report(results, days)
        report_file = f'backtest_report_{timestamp}.md'
        with open(report_file, 'w') as f:
            f.write(report)
        
        logger.info(f"📄 Report saved to {report_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Backtest buy-hold strategy')
    parser.add_argument('--days', type=int, default=30, help='Number of days to backtest')
    parser.add_argument('--pairs', type=str, default='BTC/USDT,ETH/USDT,SOL/USDT',
                       help='Comma-separated list of pairs')
    parser.add_argument('--config', type=str, default='config.json', help='Config file path')
    
    args = parser.parse_args()
    
    # Parse pairs
    pairs = [p.strip() for p in args.pairs.split(',')]
    
    # Run backtest
    backtester = BuyHoldBacktester(args.config)
    results = backtester.run_backtest(pairs, args.days)
    
    # Save results
    backtester.save_results(results, args.days)
    
    # Print summary
    print("\n🏆 Backtest Complete!")
    print(f"Tested {len(results)} pairs over {args.days} days")
    
    if results:
        avg_return = sum(m['total_return'] for m in results.values()) / len(results)
        print(f"Average Return: {avg_return:.2%}")


if __name__ == "__main__":
    main() 