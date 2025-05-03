# 根目录/data_importer.py
import pandas as pd
from sqlalchemy import create_engine, text, String, DateTime, BigInteger, Float
from sqlalchemy.exc import SQLAlchemyError
import os

DATA_PATH = r"D:\期货DB\merged_output\CF99.csv"
DB_PATH = r'sqlite:///C:\Users\Administrator\Desktop\程序化交易\AutoTrader\vnpy.db'

try:
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"数据文件未找到：{DATA_PATH}")

    # 读取 CSV 并忽略索引列
    df = pd.read_csv(DATA_PATH, index_col=0)
    
    # 添加必要字段
    df['symbol'] = 'CF99'      # 明确设置合约代码
    df['exchange'] = 'CFFEX'   # 设置交易所代码
    df['interval'] = '1m'      # 设置K线周期
    
    # 列名映射
    column_mapping = {
        'datetime': 'datetime',
        'open': 'open_price',
        'high': 'high_price',
        'low': 'low_price',
        'close': 'close_price',
        'volume': 'volume'
    }
    df = df.rename(columns=column_mapping)
    
    # 类型转换
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    engine = create_engine(DB_PATH)
    
    # 插入数据（替换旧表）
    df.to_sql(
        name='dbbardata',
        con=engine,
        if_exists='replace',  # 清空旧表并重建
        index=False,
        dtype={
            'symbol': String(20),
            'exchange': String(10),
            'datetime': DateTime,
            'interval': String(3),
            'open_price': Float,
            'high_price': Float,
            'low_price': Float,
            'close_price': Float,
            'volume': BigInteger
        }
    )
    print(f"✅ 成功插入 {len(df)} 条数据")

except Exception as e:
    print(f"错误: {str(e)}")
finally:
    if 'engine' in locals():
        engine.dispose()