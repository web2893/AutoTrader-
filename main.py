# AutoTrader/main.py
import pandas as pd
import matplotlib.pyplot as plt
from database import DatabaseManager
from backtester import BacktestEngine
from strategies.Renko import RenkoStrategy
from config import config
from datetime import datetime

def plot_backtest_results(data_df, result, initial_cash):
    plt.figure(figsize=(14, 10))
    
    # 价格曲线
    ax1 = plt.subplot(211)
    data_df['close_price'].plot(ax=ax1, color='gray', label='Price')
    
    # 处理交易时间戳
    trades_df = result['trades']
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])  # 确保转换为datetime
    
    # 筛选有效买卖点（时间戳必须存在于data_df索引中）
    buy_dates = trades_df[trades_df['type'] == 'buy']['timestamp']
    valid_buy_dates = buy_dates[buy_dates.isin(data_df.index)]
    sell_dates = trades_df[trades_df['type'] == 'sell']['timestamp']
    valid_sell_dates = sell_dates[sell_dates.isin(data_df.index)]
    
    # 标记买卖点
    ax1.scatter(valid_buy_dates, data_df.loc[valid_buy_dates]['close_price'], 
               marker='^', color='g', s=100, label='Buy')
    ax1.scatter(valid_sell_dates, data_df.loc[valid_sell_dates]['close_price'],
               marker='v', color='r', s=100, label='Sell')
    ax1.set_title('Price with Trade Signals')
    ax1.legend()
    
    # 资产组合价值曲线
    ax2 = plt.subplot(212, sharex=ax1)
    result['history']['portfolio_value'].plot(ax=ax2, color='b', label='Portfolio Value')
    ax2.axhline(y=initial_cash, color='gray', linestyle='--', label='Initial Cash')
    ax2.set_title('Portfolio Value')
    ax2.legend()
    
    plt.tight_layout()
    plt.show()

def main():
    db = DatabaseManager()
    backtester = BacktestEngine()
    strategy = RenkoStrategy(brick_size=250)
    
    data = db.fetch_historical_data(
        symbol="jm2505",
        exchange="DCE",
        interval="1m",
        start=datetime.strptime(config.backtest.fromdate, "%Y-%m-%d"),
        end=datetime.strptime(config.backtest.todate, "%Y-%m-%d")
    )
    
    if not data:
        print("错误：请先运行 data_importer.py 导入测试数据")
        return
    
    columns = ['datetime', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']
    data_df = pd.DataFrame(data, columns=columns)
    data_df.rename(columns={'datetime': 'timestamp'}, inplace=True)
    data_df['timestamp'] = pd.to_datetime(data_df['timestamp'])  # 确保转换为datetime
    data_df.set_index('timestamp', inplace=True)
    
    result = backtester.run_backtest(data_df, strategy)
    
    print(f"\n回测结果：")
    print(f"初始资金: {backtester.initial_cash:.2f}")
    print(f"最终总资产: {result['total']:.2f}")
    print(f"现金余额: {result['cash']:.2f}")
    print(f"持仓价值: {result['holdings'] * data_df.iloc[-1]['close_price']:.2f}")
    
    # 可视化结果
    plot_backtest_results(data_df, result, backtester.initial_cash)

if __name__ == "__main__":
    main()