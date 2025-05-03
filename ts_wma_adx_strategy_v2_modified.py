# 文件名：ts_wma_adx_strategy_v2_modified.py
import pandas as pd
import numpy as np
from vnpy.trader.database import get_database
from vnpy.trader.object import Exchange, Interval, BarData
from datetime import datetime
from pytz import timezone
import logging
from typing import Dict, List

# -------------------- 配置日志 --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
CHINA_TZ = timezone("Asia/Shanghai")

# -------------------- 策略实现 --------------------
class WMA_ADX_Strategy:
    """基于WMA和ADX指标的策略"""
    def __init__(self, short_window=7, long_window=20, adx_threshold=25):
        self.short_window = short_window
        self.long_window = long_window
        self.adx_threshold = adx_threshold
        self.data = pd.DataFrame()

    def init(self, data: pd.DataFrame):
        """策略初始化"""
        self.data = data.copy()
        self._calculate_wma()
        self._calculate_adx()

    def _calculate_wma(self):
        """计算加权移动平均"""
        self.data['short_wma'] = self.data['close_price'].ewm(span=self.short_window).mean()
        self.data['long_wma'] = self.data['close_price'].ewm(span=self.long_window).mean()

    def _calculate_adx(self):
        """计算ADX指标（简化版）"""
        high = self.data['high_price']
        low = self.data['low_price']
        close = self.data['close_price']
        
        tr = np.maximum(high - low, np.abs(high - close.shift()), np.abs(low - close.shift()))
        atr = tr.rolling(window=14).mean()
        
        up = high.diff()
        down = -low.diff()
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        
        di_plus = (plus_dm / atr).rolling(window=14).mean() * 100
        di_minus = (minus_dm / atr).rolling(window=14).mean() * 100
        self.data['adx'] = np.abs(di_plus - di_minus) / (di_plus + di_minus) * 100

    def generate_signals(self, row: pd.Series, engine) -> List[Dict]:
        """生成交易信号"""
        signals = []
        idx = row.name
        current_position = engine.holdings
        
        if idx < max(self.short_window, self.long_window, 14):
            return signals
        
        crossover = (self.data.loc[idx, 'short_wma'] > self.data.loc[idx, 'long_wma']) and \
                   (self.data.loc[idx-1, 'short_wma'] <= self.data.loc[idx-1, 'long_wma'])
        crossunder = (self.data.loc[idx, 'short_wma'] < self.data.loc[idx, 'long_wma']) and \
                    (self.data.loc[idx-1, 'short_wma'] >= self.data.loc[idx-1, 'long_wma'])
        
        adx_ok = self.data.loc[idx, 'adx'] > self.adx_threshold
        
        if crossover and adx_ok and current_position <= 0:
            signals.append({
                "timestamp": idx,
                "type": "buy",
                "quantity": 1
            })
        elif crossunder and current_position > 0:
            signals.append({
                "timestamp": idx,
                "type": "sell",
                "quantity": current_position
            })
            
        return signals

# -------------------- 主函数 --------------------
def main():
    # 使用vnpy的get_database获取数据库实例
    database = get_database()
    config = {
        "symbol": "JM2505",
        "exchange": "DCE",
        "interval": "15min",
        "fromdate": "2024-01-01",
        "todate": "2024-04-01",
        "short_window": 7,
        "long_window": 20,
        "adx_threshold": 25,
        "initial_cash": 1e6,
        "commission": 0.001,
        "slippage": 0.0
    }
    
    # 初始化回测引擎
    backtester = BacktestEngine()
    backtester.set_parameters(
        capital=config["initial_cash"],
        commission=config["commission"],
        slippage=config["slippage"]
    )
    
    # 获取历史数据
    data_df = database.load_bar_data(
        symbol=config["symbol"],
        exchange=Exchange(config["exchange"]),
        interval=Interval(config["interval"]),
        start=datetime.strptime(config["fromdate"], "%Y-%m-%d"),
        end=datetime.strptime(config["todate"], "%Y-%m-%d")
    )
    
    if data_df.empty:
        logger.error("数据获取失败，请检查参数")
        return
    
    # 转换数据格式为DataFrame（假设数据格式需要调整）
    data_df = pd.DataFrame([{
        'datetime': bar.datetime,
        'open_price': bar.open_price,
        'high_price': bar.high_price,
        'low_price': bar.low_price,
        'close_price': bar.close_price,
        'volume': bar.volume
    } for bar in data_df])
    data_df.set_index('datetime', inplace=True)
    
    # 初始化策略
    strategy = WMA_ADX_Strategy(
        short_window=config["short_window"],
        long_window=config["long_window"],
        adx_threshold=config["adx_threshold"]
    )
    strategy.init(data_df)
    
    # 运行回测
    backtester.run_backtest(
        strategy=strategy,
        data=data_df
    )
    
    # 输出结果（需确保BacktestEngine支持以下方法）
    result = backtester.calculate_result()
    print("\n=== 回测结果 ===")
    print(f"初始资金: {config['initial_cash']:,.2f}")
    print(f"最终总资产: {result['total_asset']:,.2f}")
    print(f"交易次数: {len(result['trades'])}次")
    
    # 绘图（需自行实现或使用vnpy内置方法）
    # backtester.show_chart()

if __name__ == "__main__":
    main()