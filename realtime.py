# AutoTrader/realtime.py
from exchange import ExchangeAPI
import time

def collect_realtime_data():
    api = ExchangeAPI()  # 初始化CTP连接
    while True:
        time.sleep(1)  # 持续运行以接收数据

if __name__ == "__main__":
    collect_realtime_data()