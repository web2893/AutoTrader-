# AutoTrader/main.py
import pandas as pd
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit)
from PyQt5.QtChart import QChart, QChartView, QLineSeries
from PyQt5.QtCore import Qt, QDateTime
from database import DatabaseManager
from backtester import BacktestEngine
from strategies.dual_ma import DualMAStrategy
from config import config

class TradingGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.backtester = BacktestEngine()
        self.strategy = DualMAStrategy()
        self.initUI()
        self.setup_chart()

    def initUI(self):
        self.setWindowTitle('AutoTrader Pro')
        self.setGeometry(300, 300, 1200, 800)

        # 主控件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # 左侧控制面板
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        # 参数输入
        self.symbol_input = QLineEdit("BTC/USDT")
        self.from_date = QLineEdit(config.backtest.fromdate)
        self.to_date = QLineEdit(config.backtest.todate)
        
        control_layout.addWidget(QLabel("交易对:"))
        control_layout.addWidget(self.symbol_input)
        control_layout.addWidget(QLabel("开始日期:"))
        control_layout.addWidget(self.from_date)
        control_layout.addWidget(QLabel("结束日期:"))
        control_layout.addWidget(self.to_date)

        # 回测按钮
        self.run_btn = QPushButton("执行回测")
        self.run_btn.clicked.connect(self.run_backtest)
        control_layout.addWidget(self.run_btn)

        # 结果显示
        self.result_display = QTextEdit()
        control_layout.addWidget(QLabel("回测结果:"))
        control_layout.addWidget(self.result_display)

        layout.addWidget(control_panel, stretch=1)

        # 右侧图表
        self.chart_view = QChartView()
        layout.addWidget(self.chart_view, stretch=3)

    def setup_chart(self):
        self.chart = QChart()
        self.chart.setTitle("价格与策略信号")
        self.chart_view.setChart(self.chart)

    def run_backtest(self):
        try:
            # 获取数据
            data = self.db.fetch_historical_data(
                self.symbol_input.text(),
                self.from_date.text(),
                self.to_date.text()
            )
            data_df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
            
            # 执行回测
            result = self.backtester.run_backtest(data_df, self.strategy)
            
            # 更新界面
            self.show_results(data_df, result)
            
        except Exception as e:
            self.result_display.setText(f"错误发生: {str(e)}")

    def show_results(self, data, result):
        # 显示文本结果
        result_text = f"""回测结果:
        总收益率: {result['returns']:.2%}
        夏普比率: {result['sharpe']:.2f}
        最大回撤: {result['drawdown']:.2%}
        """
        self.result_display.setText(result_text)

        # 绘制价格曲线
        self.chart.removeAllSeries()
        
        price_series = QLineSeries()
        for i, row in data.iterrows():
            price_series.append(i, row['close'])
        
        price_series.setName("收盘价")
        self.chart.addSeries(price_series)
        self.chart.createDefaultAxes()
        self.chart.axisY().setTitleText("价格")

def main():
    app = QApplication(sys.argv)
    gui = TradingGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()