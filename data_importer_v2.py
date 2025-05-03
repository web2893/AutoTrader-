# 根目录/data_importer_v2.py
import pandas as pd
import glob
import os
from datetime import timedelta
from dateutil.parser import parse
from pytz import timezone
import logging
from pathlib import Path

# 添加vnpy依赖
from vnpy.trader.object import BarData, Exchange, Interval
from vnpy.trader.database import BaseDatabase

# ------------ 显式配置SQLite数据库 ------------
from vnpy_sqlite.sqlite_database import SqliteDatabase  # 确保已安装vnpy_sqlite

# 初始化数据库驱动（移除init()调用）
database: BaseDatabase = SqliteDatabase()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ------------ 其他代码完全保持不变 ------------
CHINA_TZ = timezone("Asia/Shanghai")

def extract_vt_data_type(vt_data_type: str):
    """合约符号解析"""
    parts = vt_data_type.split(".")
    if len(parts) == 2:
        symbol = parts[0]
        exchange = Exchange(parts[1].upper())
        return symbol, exchange
    else:
        raise ValueError(f"Invalid vt_data_type: {vt_data_type}")

def get_variety(symbol: str) -> str:
    """品种提取"""
    return "".join(filter(str.isalpha, symbol)).upper()

def order_book_id_to_vt_data_type(order_book_id: str) -> str:
    """合约转换逻辑"""
    order_book_id = order_book_id.upper()
    parts = order_book_id.split(".")
    symbol = parts[0]
    variety = get_variety(symbol)
    
    # 交易所判断逻辑
    if len(parts) > 1:
        exchange = Exchange(parts[1].upper())
    else:
        # 此处可添加更复杂的交易所推断逻辑
        exchange = Exchange.SHFE  # 默认上期所
    
    # CZCE特殊处理
    if exchange == Exchange.CZCE:
        symbol = variety + symbol.replace(variety, "")[1:]
    return f"{symbol}.{exchange.value}"

# ------------ 数据导入逻辑 ------------
DATA_DIR = r"D:\期货DB\merged_output\CF99.csv"  # CSV文件路径

def process_file(file_path: str):
    """处理单个CSV文件"""
    try:
        # 读取CSV并统一列名小写
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower()
        
        # 时间列处理
        time_column = "datetime" if "datetime" in df.columns else "date"
        df[time_column] = pd.to_datetime(df[time_column])
        
        bars = []
        for _, row in df.iterrows():
            # 时间处理（移植第一个脚本逻辑）
            if "date" in df.columns:  # 日线数据
                dt = CHINA_TZ.localize(parse(str(row["date"])))
                interval = Interval.DAILY
            else:  # 分钟线数据
                raw_dt = parse(str(row["datetime"]))
                dt = CHINA_TZ.localize(raw_dt - timedelta(minutes=1))
                interval = Interval.MINUTE
            
            # 合约转换（假设数据库为database1规则）
            order_book_id = f"{row['variety']}{row['data_type']}"
            vt_data_type = order_book_id_to_vt_data_type(order_book_id)
            symbol, exchange = extract_vt_data_type(vt_data_type)
            
            # 构建Bar对象
            bar = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=interval,
                open_price=row["open"],
                high_price=row["high"],
                low_price=row["low"],
                close_price=row["close"],
                volume=row.get("volume", 0),
                open_interest=row.get("open_interest", 0),
                gateway_name="IMPORT"
            )
            bars.append(bar)
        
        # 使用vnpy数据库接口保存
        if bars:
            database.save_bar_data(bars)
            logger.info(f"✅成功写入 {len(bars)} 条数据 -> {os.path.basename(file_path)}")
    
    except Exception as e:
        logger.error(f"文件处理失败 {file_path}: {str(e)}")

if __name__ == "__main__":
    # 获取所有CSV文件
    files = glob.glob(DATA_DIR)
    if not files:
        raise FileNotFoundError(f"未找到CSV文件: {DATA_DIR}")
    
    # 按文件名排序处理
    for file in sorted(files, key=lambda x: os.path.basename(x)):
        logger.info(f"正在处理: {os.path.basename(file)}")
        process_file(file)
    
    logger.info("✅全部数据导入完成！")