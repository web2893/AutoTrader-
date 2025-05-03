# main_v2a.py
import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
from vnpy.trader.database import get_database
from vnpy.trader.object import Exchange, Interval, BarData
from datetime import datetime
from pytz import timezone
import logging
from typing import Dict, List

# -------------------- 添加项目根目录到PATH --------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -------------------- 配置日志 --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
CHINA_TZ = timezone("Asia/Shanghai")

# -------------------- 回测引擎实现 --------------------
class BacktestEngine:
    """支持动态持仓和交易成本的回测引擎"""
    def __init__(
        self,
        initial_cash: float = 1e6,
        commission: float = 0.001,
        slippage: float = 0.0
    ):
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage
        self.reset()

    def reset(self):
        self.cash = self.initial_cash
        self.holdings = 0
        self.trades: List[Dict] = []
        self.history = []

    def execute_trade(self, signal: Dict, price: float):
        if signal["type"] not in ["buy", "sell"]:
            logger.warning(f"无效交易类型: {signal['type']}")
            return

        executed_price = price * (1 + self.slippage) if signal["type"] == "buy" else price * (1 - self.slippage)
        quantity = signal["quantity"]
        trade_value = executed_price * quantity
        commission_cost = trade_value * self.commission

        if signal["type"] == "buy":
            total_cost = trade_value + commission_cost
            if self.cash < total_cost:
                logger.warning(f"资金不足，所需资金: {total_cost:.2f}, 当前现金: {self.cash:.2f}")
                return
            self.cash -= total_cost
            self.holdings += quantity
        else:
            if self.holdings < quantity:
                logger.warning(f"持仓不足，当前持仓: {self.holdings}, 尝试卖出: {quantity}")
                return
            self.cash += (trade_value - commission_cost)
            self.holdings -= quantity

        self.trades.append({
            "timestamp": signal["timestamp"],
            "type": signal["type"],
            "price": executed_price,
            "quantity": quantity,
            "commission": commission_cost,
            "cash_after": self.cash,
            "holdings_after": self.holdings
        })

    def run_backtest(self, data: pd.DataFrame, strategy) -> Dict:
        self.reset()
        strategy.init(data)

        for idx, row in data.iterrows():
            signals = strategy.generate_signals(row, self)
            for signal in signals:
                self.execute_trade(signal, row["close_price"])
            
            current_value = self.cash + self.holdings * row["close_price"]
            self.history.append({
                "timestamp": idx,
                "portfolio_value": current_value,
                "cash": self.cash,
                "holdings_value": self.holdings * row["close_price"],
                "price": row["close_price"]
            })

        return {
            "total": self.cash + self.holdings * data.iloc[-1]["close_price"],
            "cash": self.cash,
            "holdings": self.holdings,
            "trades": pd.DataFrame(self.trades),
            "history": pd.DataFrame(self.history).set_index("timestamp"),
            "last_price": data.iloc[-1]["close_price"]
        }

# -------------------- 数据库管理器 --------------------
class DatabaseManager:
    def __init__(self):
        self.database = get_database()

    def _convert_symbol(self, raw_symbol: str, exchange: Exchange) -> str:
        variety = ''.join(filter(str.isalpha, raw_symbol)).upper()
        contract_no = ''.join(filter(str.isdigit, raw_symbol))
        if exchange == Exchange.CZCE:
            year = contract_no[0]
            month = contract_no[1:]
            return f"{variety}{year}{month}".upper()
        return raw_symbol.lower() if exchange != Exchange.CFFEX else raw_symbol.upper()

    def fetch_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        try:
            exchange_enum = getattr(Exchange, exchange.upper())
            converted_symbol = self._convert_symbol(symbol, exchange_enum)
            interval_enum = Interval.MINUTE if interval == "1m" else Interval.DAILY
            start = CHINA_TZ.localize(start) if start.tzinfo is None else start.astimezone(CHINA_TZ)
            end = CHINA_TZ.localize(end) if end.tzinfo is None else end.astimezone(CHINA_TZ)
            
            bars = self.database.load_bar_data(
                symbol=converted_symbol,
                exchange=exchange_enum,
                interval=interval_enum,
                start=start,
                end=end
            )
            
            data = []
            for bar in bars:
                data.append({
                    "timestamp": bar.datetime,
                    "open_price": bar.open_price,
                    "high_price": bar.high_price,
                    "low_price": bar.low_price,
                    "close_price": bar.close_price,
                    "volume": bar.volume,
                    "open_interest": bar.open_interest
                })
            return pd.DataFrame(data).set_index("timestamp")
        except Exception as e:
            logger.error(f"数据获取失败: {str(e)}")
            return pd.DataFrame()

# -------------------- 可视化函数 --------------------
def plot_backtest_results(data_df, result, initial_cash, symbol):
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.figure(figsize=(14, 10))
    
    ax1 = plt.subplot(211)
    data_df['close_price'].plot(ax=ax1, color='dimgray', label='价格', lw=1)
    
    trades_df = result['trades']
    if not trades_df.empty:
        buy_dates = trades_df[trades_df['type'] == 'buy']['timestamp']
        sell_dates = trades_df[trades_df['type'] == 'sell']['timestamp']
        ax1.scatter(buy_dates, data_df.loc[buy_dates]['close_price'],
                   marker='^', color='limegreen', s=100, label='买入')
        ax1.scatter(sell_dates, data_df.loc[sell_dates]['close_price'],
                   marker='v', color='crimson', s=100, label='卖出')
    ax1.set_title(f'{symbol} 价格走势与交易信号')  # 添加品种名称
    ax1.legend()
    
    ax2 = plt.subplot(212, sharex=ax1)
    result['history']['portfolio_value'].plot(
        ax=ax2, color='royalblue', label='组合净值', lw=1.5
    )
    ax2.axhline(initial_cash, color='gray', ls='--', label='初始资金')
    ax2.set_title(f'{symbol} 资金曲线')  # 添加品种名称
    ax2.legend()
    
    plt.tight_layout()
    plt.show()

# -------------------- 策略适配器 --------------------
class StrategyAdapter:
    def __init__(self, external_strategy):
        self.strategy = external_strategy
        
    def init(self, data: pd.DataFrame):
        pass
        
    def generate_signals(self, row: pd.Series, engine: BacktestEngine) -> List[Dict]:
        signal = self.strategy.generate_signal(row)
        if signal[0] == "hold":
            return []
            
        return [{
            "timestamp": row.name,
            "type": signal[0],
            "quantity": signal[1]
        }]

# -------------------- 主函数 --------------------
def main():
    from strategies.Renko import RenkoStrategy as ExternalRenkoStrategy

    db = DatabaseManager()
    
    config = {
        "symbol": "JM2509",
        "exchange": "DCE",
        "interval": "5m",
        "fromdate": "2024-01-01",
        "todate": "2025-04-30",
        "brick_size": 30,
        "fixed_quantity": 1,
        "initial_cash": 1000000,
        "commission": 0.001,
        "slippage": 0.005
    }
    
    backtester = BacktestEngine(
        initial_cash=config["initial_cash"],
        commission=config["commission"],
        slippage=config["slippage"]
    )
    
    try:
        external_strategy = ExternalRenkoStrategy(
            brick_size=config["brick_size"],
            fixed_quantity=config["fixed_quantity"]
        )
        strategy = StrategyAdapter(external_strategy)
    except Exception as e:
        logger.error(f"策略初始化失败: {str(e)}")
        return
    
    data_df = db.fetch_historical_data(
        symbol=config["symbol"],
        exchange=config["exchange"],
        interval=config["interval"],
        start=datetime.strptime(config["fromdate"], "%Y-%m-%d"),
        end=datetime.strptime(config["todate"], "%Y-%m-%d")
    )
    
    if data_df.empty:
        logger.error("获取数据失败，请检查：1.数据库连接 2.合约代码规则 3.时间范围")
        return
    
    result = backtester.run_backtest(data_df, strategy)
    
    print("\n=== 回测结果 ===")
    print(f"初始资金: {config['initial_cash']:,.2f}")
    print(f"最终总资产: {result['total']:,.2f}")
    print(f"现金余额: {result['cash']:,.2f}")
    print(f"持仓价值: {result['holdings'] * result['last_price']:,.2f}")
    print(f"交易次数: {len(result['trades'])}次")
    
    plot_backtest_results(data_df, result, config["initial_cash"], config["symbol"])  # 传入品种名称

if __name__ == "__main__":
    main()