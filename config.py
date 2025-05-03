# AutoTrader/config.py
import os
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    """数据库配置（VN Py兼容）"""
    driver: str = "sqlite"
    database: str = "database.db"
    
    @property
    def connection_string(self):
        if self.driver == "sqlite":
            return f"sqlite:///{os.path.abspath(r'C:\Users\Administrator\.vntrader\database.db')}"

@dataclass
class BacktestConfig:
    initial_cash: int = 100000
    fromdate: str = "2024-01-01"  # 确保与实际数据时间匹配
    todate: str = "2025-03-30"    # 示例时间范围

class Config:
    def __init__(self):
        self.database = DatabaseConfig()
        self.backtest = BacktestConfig()

config = Config()