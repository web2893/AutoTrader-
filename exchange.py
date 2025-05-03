# AutoTrader/exchange.py
from ctpmd import CtpMdApi  # 假设使用第三方CTP接口库
from config import config
from database import DatabaseManager
import logging

logger = logging.getLogger(__name__)

class CTPMarketData(CtpMdApi):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        
    def OnFrontConnected(self):
        """CTP连接成功回调"""
        req = {
            "BrokerID": config.exchange.broker_id,
            "UserID": config.exchange.user_id,
            "Password": config.exchange.password
        }
        self.ReqUserLogin(req, 0)
        logger.info("CTP行情连接成功")

    def OnRtnDepthMarketData(self, data):
        """实时行情推送"""
        try:
            with self.db.session_scope() as session:
                session.execute(
                    """INSERT INTO price_data 
                    (symbol, timestamp, open, high, low, close, volume)
                    VALUES (:symbol, :ts, :open, :high, :low, :close, :vol)""",
                    {
                        "symbol": data.InstrumentID,
                        "ts": data.UpdateTime,
                        "open": data.OpenPrice,
                        "high": data.HighestPrice,
                        "low": data.LowestPrice,
                        "close": data.LastPrice,
                        "vol": data.Volume
                    }
                )
            logger.debug(f"存入行情数据: {data.InstrumentID}@{data.LastPrice}")
        except Exception as e:
            logger.error(f"数据存储失败: {e}")

class ExchangeAPI:
    """统一交易所接口"""
    def __init__(self):
        if config.exchange.name == "ctp":
            self.client = CTPMarketData()
            self.client.RegisterFront(config.exchange.md_front)
            self.client.Init()
        else:
            raise NotImplementedError("仅支持CTP交易所")