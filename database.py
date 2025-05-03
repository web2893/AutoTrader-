# AutoTrader/database.py
from sqlalchemy import create_engine, text, Column, String, DateTime, Float, Integer, BigInteger, Date
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from config import config
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class DbBarData(Base):
    """K线数据表 (兼容VN Py)"""
    __tablename__ = 'dbbardata'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(10), nullable=False)
    datetime = Column(DateTime, nullable=False)
    interval = Column(String(3))
    volume = Column(BigInteger)
    open_interest = Column(BigInteger)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    turnover = Column(Float)

class DatabaseManager:
    def __init__(self):
        self._configure_engine()
        self._initialize_database()
        self._verify_connection()
        self.Session = sessionmaker(bind=self.engine)

    def _configure_engine(self):
        connect_args = {}
        if 'sqlite' in config.database.connection_string:
            connect_args['check_same_thread'] = False
        
        self.engine = create_engine(
            config.database.connection_string,
            pool_pre_ping=True,
            connect_args=connect_args
        )

    def _initialize_database(self):
        try:
            Base.metadata.create_all(self.engine)
            logger.info("✅ 成功创建/验证表结构")
        except SQLAlchemyError as e:
            logger.error(f"❌ 表结构初始化失败: {str(e)}")
            raise

    def _verify_connection(self):
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ 数据库连接验证成功")
        except SQLAlchemyError as e:
            logger.error(f"❌ 数据库连接失败: {str(e)}")
            raise

    @contextmanager
    def session_scope(self):
        session = self.Session()
        try:
            yield session
            session.commit()
            logger.debug("事务提交成功")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"事务回滚: {str(e)}")
            raise
        finally:
            session.close()

    def fetch_historical_data(self, symbol: str, exchange: str, interval: str, start: datetime, end: datetime) -> list:
        query = text("""
            SELECT datetime, open_price, high_price, low_price, close_price, volume
            FROM dbbardata
            WHERE symbol = :symbol
                AND exchange = :exchange
                AND interval = :interval
                AND datetime BETWEEN :start AND :end
            ORDER BY datetime ASC
        """)

        params = {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "interval": interval,
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            with self.session_scope() as session:
                result = session.execute(query, params)
                data = [tuple(row) for row in result]
                logger.info(f"✅ 成功获取 {len(data)} 条数据")
                return data
        except SQLAlchemyError as e:
            logger.error(f"查询失败: {str(e)}")
            return []