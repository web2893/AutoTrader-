# main_vnpy.py
import pandas as pd
import matplotlib.pyplot as plt
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

# -------------------- 回测引擎实现 --------------------
class BacktestEngine:
    """支持动态持仓和交易成本的回测引擎（修正手续费和滑点）"""
    def __init__(
        self,
        initial_cash: float = 1e6,
        commission_per_lot: float = 30.0,  # 每手固定手续费（单位：元）
        slippage: float = 0.5              # 滑点（固定点数）
    ):
        self.initial_cash = initial_cash
        self.commission_per_lot = commission_per_lot
        self.slippage = slippage
        self.reset()

    def reset(self):
        """重置回测状态"""
        self.cash = self.initial_cash
        self.holdings = 0          # 当前持仓数量（单位：手）
        self.trades: List[Dict] = []  # 交易记录列表
        self.history = []          # 每日资产记录

    def execute_trade(self, signal: Dict, price: float):
        """
        执行交易并更新状态（修正手续费和滑点计算）
        :param signal: 交易信号字典，需包含type(buy/sell), quantity
        :param price: 当前K线的收盘价
        """
        if signal["type"] not in ["buy", "sell"]:
            logger.warning(f"无效交易类型: {signal['type']}")
            return

        # 计算实际成交价格（考虑滑点）
        if signal["type"] == "buy":
            executed_price = price + self.slippage  # 买入加滑点
        else:
            executed_price = price - self.slippage  # 卖出减滑点

        # 计算手续费（固定费用）
        quantity = signal["quantity"]
        commission_cost = self.commission_per_lot * quantity

        # 执行买入逻辑
        if signal["type"] == "buy":
            total_cost = executed_price * quantity + commission_cost
            if self.cash < total_cost:
                logger.warning(f"资金不足，所需资金: {total_cost:.2f}, 当前现金: {self.cash:.2f}")
                return
            self.cash -= total_cost
            self.holdings += quantity
            logger.info(f"买入 {quantity} 手 @ {executed_price:.2f}")

        # 执行卖出逻辑
        else:
            if self.holdings < quantity:
                logger.warning(f"持仓不足，当前持仓: {self.holdings}, 尝试卖出: {quantity}")
                return
            total_income = executed_price * quantity - commission_cost
            self.cash += total_income
            self.holdings -= quantity
            logger.info(f"卖出 {quantity} 手 @ {executed_price:.2f}")

        # 记录交易详情
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
        """
        运行回测主逻辑
        :param data: 包含OHLCV数据的DataFrame
        :param strategy: 交易策略对象
        :return: 包含回测结果的字典
        """
        self.reset()
        strategy.init(data)

        for idx, row in data.iterrows():
            # 生成交易信号
            signals = strategy.generate_signals(row, self)
            
            # 执行所有信号
            for signal in signals:
                self.execute_trade(signal, row["close_price"])
            
            # 记录每日资产状态（使用当前价格计算持仓价值）
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
    """从vn.py数据库获取历史数据"""
    def __init__(self):
        self.database = get_database()

    def _convert_symbol(self, raw_symbol: str, exchange: Exchange) -> str:
        """转换合约符号（根据交易所规则）"""
        variety = ''.join(filter(str.isalpha, raw_symbol)).upper()
        contract_no = ''.join(filter(str.isdigit, raw_symbol))

        # 郑商所特殊处理
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
        """获取历史数据"""
        try:
            exchange_enum = getattr(Exchange, exchange.upper())
            converted_symbol = self._convert_symbol(symbol, exchange_enum)
            interval_enum = Interval.MINUTE if interval == "1m" else Interval.DAILY
            
            # 处理时区
            start = CHINA_TZ.localize(start) if start.tzinfo is None else start.astimezone(CHINA_TZ)
            end = CHINA_TZ.localize(end) if end.tzinfo is None else end.astimezone(CHINA_TZ)
            
            # 查询数据库
            bars = self.database.load_bar_data(
                symbol=converted_symbol,
                exchange=exchange_enum,
                interval=interval_enum,
                start=start,
                end=end
            )
            
            # 转换为DataFrame
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
def plot_backtest_results(data_df, result, initial_cash):
    """绘制回测结果"""
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.figure(figsize=(14, 10))
    
    # 价格与买卖信号
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
    ax1.set_title('价格走势与交易信号')
    ax1.legend()
    
    # 资金曲线
    ax2 = plt.subplot(212, sharex=ax1)
    result['history']['portfolio_value'].plot(
        ax=ax2, color='royalblue', label='组合净值', lw=1.5
    )
    ax2.axhline(initial_cash, color='gray', ls='--', label='初始资金')
    ax2.set_title('资金曲线')
    ax2.legend()
    
    plt.tight_layout()
    plt.show()

# -------------------- 示例策略 --------------------
class RenkoStrategy:
    """基于价格突破的Renko策略示例"""
    def __init__(self, brick_size=30):
        self.brick_size = brick_size
        
    def init(self, data: pd.DataFrame):
        logger.info(f"策略初始化，砖块大小: {self.brick_size}点")
        
    def generate_signals(self, row: pd.Series, engine: BacktestEngine) -> List[Dict]:
        signals = []
        current_holdings = engine.holdings
        
        # 多头信号：无持仓时买入
        if (row["close_price"] - row["open_price"] >= self.brick_size) and current_holdings == 0:
            signals.append({
                "timestamp": row.name,
                "type": "buy",
                "quantity": 1  # 每次交易1手
            })
            
        # 空头信号：有持仓时卖出
        elif (row["open_price"] - row["close_price"] >= self.brick_size) and current_holdings > 0:
            signals.append({
                "timestamp": row.name,
                "type": "sell",
                "quantity": current_holdings  # 平全部仓位
            })
            
        return signals

# -------------------- 主函数 --------------------
def main():
    db = DatabaseManager()
    
    # 回测参数配置（注意调整时间范围和合约代码）
    config = {
        "symbol": "JM2505",       # 合约代码（示例）
        "exchange": "DCE",        # 商品交易所
        "interval": "15m",        # K线周期
        "fromdate": "2024-06-01", # 开始日期
        "todate": "2025-04-30",   # 结束日期
        "brick_size": 30,         # Renko砖块大小
        "initial_cash": 100000,  # 初始资金（单位：元）
        "commission_per_lot": 30.0,  # 每手固定手续费（单位：元）
        "slippage": 0.5           # 滑点（固定点数）
    }
    
    # 初始化回测引擎
    backtester = BacktestEngine(
        initial_cash=config["initial_cash"],
        commission_per_lot=config["commission_per_lot"],
        slippage=config["slippage"]
    )
    
    # 初始化策略
    try:
        strategy = RenkoStrategy(brick_size=config["brick_size"])
    except Exception as e:
        logger.error(f"策略初始化失败: {str(e)}")
        return
    
    # 获取历史数据
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
    
    # 运行回测
    result = backtester.run_backtest(data_df, strategy)
    
    # 打印结果
    print("\n=== 回测结果 ===")
    print(f"初始资金: {config['initial_cash']:,.2f} 元")
    print(f"最终总资产: {result['total']:,.2f} 元")
    print(f"现金余额: {result['cash']:,.2f} 元")
    print(f"持仓价值: {result['holdings'] * result['last_price']:,.2f} 元")
    print(f"交易次数: {len(result['trades'])} 次")
    
    # 绘制图表
    plot_backtest_results(data_df, result, config["initial_cash"])

if __name__ == "__main__":
    main()