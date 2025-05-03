# AutoTrader/backtester.py
import pandas as pd
from config import config

class BacktestEngine:
    def __init__(self, initial_cash=100000):
        self.initial_cash = initial_cash
        
    def run_backtest(self, data, strategy):
        cash = self.initial_cash
        holdings = 0
        history = []
        trades = []
        portfolio_values = []

        for index, row in data.iterrows():
            signal = strategy.generate_signal(row)
            signal_type, quantity = signal
            price = row['close_price']
            
            # 执行交易
            if signal_type == 'buy' and cash > 0:
                max_quantity = cash // price
                buy_quantity = min(quantity, max_quantity)
                cost = buy_quantity * price
                if cost > cash:
                    buy_quantity = cash // price
                    cost = buy_quantity * price
                holdings += buy_quantity
                cash -= cost
                trades.append({
                    'timestamp': index,  # 直接使用数据的datetime索引
                    'type': 'buy',
                    'price': price,
                    'quantity': buy_quantity
                })
            elif signal_type == 'sell' and holdings > 0:
                sell_value = holdings * price
                cash += sell_value
                trades.append({
                    'timestamp': index,  # 直接使用数据的datetime索引
                    'type': 'sell',
                    'price': price,
                    'quantity': holdings
                })
                holdings = 0
            
            # 记录资产组合价值
            portfolio_value = cash + holdings * price
            history.append({
                'timestamp': index,
                'cash': cash,
                'holdings': holdings,
                'portfolio_value': portfolio_value,
                'price': price
            })
            portfolio_values.append(portfolio_value)

        final_price = data.iloc[-1]['close_price'] if not data.empty else 0
        total = cash + holdings * final_price
        
        return {
            'total': total,
            'cash': cash,
            'holdings': holdings,
            'history': pd.DataFrame(history).set_index('timestamp'),
            'trades': pd.DataFrame(trades),
            'portfolio_values': portfolio_values
        }