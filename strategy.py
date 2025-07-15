#!/usr/bin/env python3
"""
🚀 Minimal Trading Strategy - Smart Buy-Hold
The simplest strategy that beats complex algorithms
"""

import json
import logging
from datetime import datetime
from typing import Dict, List

import ccxt
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SmartBuyHoldStrategy:
    """Smart buy-and-hold strategy with pair selection"""
    
    def __init__(self, config_path: str = 'config.json'):
        """Initialize strategy with configuration"""
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.exchange = None
        self.positions: Dict[str, Dict[str, float]] = {}
        self.performance: Dict[str, float] = {}
        
    def connect_exchange(self) -> None:
        """Connect to exchange"""
        exchange_config = self.config['exchange']
        
        self.exchange = getattr(ccxt, exchange_config['name'])({
            'apiKey': exchange_config.get('api_key'),
            'secret': exchange_config.get('api_secret'),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        logger.info(f"✅ Connected to {exchange_config['name']}")
        
    def select_pairs(self) -> List[str]:
        """Select best performing pairs based on momentum"""
        pairs = self.config['pairs']
        
        if self.config.get('dynamic_selection', False):
            # Rank pairs by recent performance
            performance_data = {}
            
            for pair in pairs:
                try:
                    # Get 30-day performance
                    if self.exchange:
                        ohlcv = self.exchange.fetch_ohlcv(pair, '1d', limit=30)
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        
                        # Calculate momentum
                        returns = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]
                        performance_data[pair] = returns
                    else:
                        performance_data[pair] = 0
                    
                except Exception as e:
                    logger.warning(f"Failed to get data for {pair}: {e}")
                    performance_data[pair] = 0
            
            # Sort by performance and select top N
            sorted_pairs = sorted(performance_data.items(), key=lambda x: x[1], reverse=True)
            selected = [pair for pair, _ in sorted_pairs[:self.config.get('max_pairs', 5)]]
            
            logger.info(f"📊 Selected pairs: {selected}")
            return selected
        
        return pairs
    
    def calculate_position_sizes(self, pairs: List[str]) -> Dict[str, float]:
        """Calculate position size for each pair"""
        total_capital = self.config['capital']
        allocation = self.config.get('allocation', 'equal')
        
        if allocation == 'equal':
            # Equal weight allocation
            size_per_pair = total_capital / len(pairs)
            return {pair: size_per_pair for pair in pairs}
        
        elif allocation == 'momentum':
            # Allocate more to better performers
            performance_data = {}
            
            for pair in pairs:
                try:
                    if self.exchange:
                        ohlcv = self.exchange.fetch_ohlcv(pair, '1d', limit=30)
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        returns = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]
                        performance_data[pair] = max(0, returns)  # Only positive returns
                    else:
                        performance_data[pair] = 0
                except Exception:
                    performance_data[pair] = 0
            
            # Normalize weights
            total_weight = sum(performance_data.values())
            if total_weight > 0:
                weights = {pair: perf / total_weight for pair, perf in performance_data.items()}
            else:
                weights = {pair: 1 / len(pairs) for pair in pairs}
            
            return {pair: total_capital * weight for pair, weight in weights.items()}
        
        return {pair: total_capital / len(pairs) for pair in pairs}
    
    def execute_trades(self):
        """Execute buy orders for selected pairs"""
        pairs = self.select_pairs()
        position_sizes = self.calculate_position_sizes(pairs)
        
        for pair, size in position_sizes.items():
            try:
                # Get current price
                ticker = self.exchange.fetch_ticker(pair)
                price = ticker['last']
                
                # Calculate amount
                amount = size / price
                
                # Place market buy order
                if self.config.get('live_trading', False):
                    _ = self.exchange.create_market_buy_order(pair, amount)
                    logger.info(f"✅ Bought {amount:.4f} {pair} at {price:.2f}")
                else:
                    logger.info(f"📝 [PAPER] Would buy {amount:.4f} {pair} at {price:.2f}")
                
                # Record position
                self.positions[pair] = {
                    'amount': amount,
                    'entry_price': price,
                    'entry_time': datetime.now().isoformat(),
                    'size_usd': size
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to buy {pair}: {e}")
    
    def check_performance(self):
        """Check current performance of positions"""
        total_value = 0
        total_cost = 0
        
        for pair, position in self.positions.items():
            try:
                ticker = self.exchange.fetch_ticker(pair)
                current_price = ticker['last']
                
                current_value = position['amount'] * current_price
                cost = position['size_usd']
                
                profit = current_value - cost
                profit_pct = (profit / cost) * 100
                
                total_value += current_value
                total_cost += cost
                
                logger.info(f"{pair}: ${current_value:.2f} ({profit_pct:+.2f}%)")
                
            except Exception as e:
                logger.error(f"Failed to check {pair}: {e}")
        
        if total_cost > 0:
            total_profit = total_value - total_cost
            total_profit_pct = (total_profit / total_cost) * 100
            
            logger.info(f"\n📊 Total Portfolio: ${total_value:.2f} ({total_profit_pct:+.2f}%)")
            logger.info(f"💰 Total Profit: ${total_profit:.2f}")
    
    def rebalance(self):
        """Rebalance portfolio if configured"""
        if not self.config.get('rebalancing', {}).get('enabled', False):
            return
        
        # Check if it's time to rebalance
        # (Implementation depends on frequency logic)
        
        logger.info("🔄 Rebalancing portfolio...")
        
        # Sell current positions
        for pair in list(self.positions.keys()):
            # Sell logic here
            pass
        
        # Buy new positions
        self.execute_trades()
    
    def run(self):
        """Run the strategy"""
        logger.info("🚀 Starting Smart Buy-Hold Strategy")
        
        # Connect to exchange
        self.connect_exchange()
        
        # Execute initial trades
        self.execute_trades()
        
        # Monitor performance
        self.check_performance()
        
        # Save state
        self.save_state()
    
    def save_state(self):
        """Save current positions to file"""
        state = {
            'positions': self.positions,
            'timestamp': datetime.now().isoformat()
        }
        
        with open('positions.json', 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info("💾 Saved positions to positions.json")


def main():
    """Main entry point"""
    strategy = SmartBuyHoldStrategy()
    strategy.run()


if __name__ == "__main__":
    main() 