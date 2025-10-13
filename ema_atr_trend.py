import pandas as pd
import talib
import numpy as np

from backtesting import Backtest, Strategy
from backtesting.lib import crossover, plot_heatmaps
from utils import load_and_process_data, merge_csv_files, send_email_notification, download_binance_data, unzip_binance_data

def custom_maximize(stats):
    # 检查交易数量和胜率有效性
    if (stats['# Trades'] < 21 or
        pd.isna(stats['Win Rate [%]'])):
        return 0
    # 直接返回胜率（百分比形式）
    return stats['Win Rate [%]']

# 设置开关
is_download_data = True  # 是否下载数据
is_batch_test = False  # 是否进行批量回测
is_send_batch_email = True  # 批量回测邮件开关
is_send_single_email = True  # 单次回测邮件开关

if is_download_data:
    download_binance_data(symbol='ETCUSDT', interval='15m', years=[2024], months=range(1, 3), save_dir='./data')
    unzip_binance_data(symbol='ETCUSDT', interval='15m', save_dir='./data')  # 添加解压调用

merged_data = merge_csv_files()
data = load_and_process_data('data/ETCUSDT-15m/ETCUSDT-15m-2024-01.csv')
# data/ETCUSDT-15m/ETCUSDT-15m-2024-01.csv
# data/BTCUSDT-15m/BTCUSDT-15m-2025-09.csv
# 测试用

print(data.head())

class EmaAtrStrategy(Strategy):
    ema_period = 45
    atr_period = 12
    multiplier = 0.59
    atr_threshold = 750  # 新增ATR波动率过滤器阈值
    rr = 1.0  # 风险回报比：止盈距离 = 止损距离 * rr

    def init(self):
        price = self.data.Close
        self.ema = self.I(talib.EMA, price, timeperiod=self.ema_period)
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=self.atr_period)

    def next(self):
        # 检查ATR波动率过滤器
        if self.atr[-1] < self.atr_threshold:
            return  # 如果ATR低于阈值，不执行交易
        
        upper = self.ema + self.atr * self.multiplier
        lower = self.ema - self.atr * self.multiplier
        
        # 计算止损和止盈距离
        sl_distance = self.atr
        tp_distance = sl_distance * self.rr  # 止盈距离 = 止损距离 * rr
        
        # 只有在空仓时才能开仓
        if self.position.size == 0:
            if crossover(self.data.Close, upper):
                self.buy(tp=self.data.Close + tp_distance, sl=self.data.Close - sl_distance)
            elif crossover(lower, self.data.Close):
                self.sell(tp=self.data.Close - tp_distance, sl=self.data.Close + sl_distance)

bt = Backtest(data, EmaAtrStrategy, cash=1_000_000_000)

if is_batch_test:
    # 定义优化参数
    ema_period_range = range(27, 66, 1)
    atr_period_range = np.arange(10, 20, 1)
    multiplier_range = list(np.arange(0.5, 0.7, 0.05))
    atr_threshold_range = list(np.arange(500, 800, 50))
    rr_range = list(np.arange(1, 2, 0.5))
    
    # 自动计算组合总数
    total_combinations = (len(ema_period_range) * len(atr_period_range) * 
                          len(multiplier_range) * len(atr_threshold_range) * len(rr_range))
    print(f"优化参数组合总数: {total_combinations}")

    stats, heatmap= bt.optimize(
        ema_period=ema_period_range,
        atr_period=atr_period_range,
        multiplier=multiplier_range,
        atr_threshold=atr_threshold_range,  # 调整ATR阈值范围
        rr=rr_range,  # 新增rr优化参数
        max_tries=10000,
        method='sambo', 
        # return_optimization=True,
        return_heatmap=True,

        # maximize='Win Rate [%]'
        maximize=custom_maximize
    )
    print(heatmap)
    plot_heatmaps(heatmap, filename='examples/heatmap_ema_atr_strategy.html', open_browser=True)
    heatmap.to_csv('result/heatmap_results3.csv', index=True)
    
    if is_send_batch_email:
        # 发送邮件提醒
        subject = "批量回测完成提醒"
        body = f"批量回测已完成。最佳胜率: {stats['Win Rate [%]']}%，交易数量: {stats['# Trades']}。"
        send_email_notification(subject, body)

else:

    stats = bt.run()
    print(stats)
    print(stats._trades)
    stats._trades.to_csv('result/trades1.csv', index=True)
    bt.plot(filename='examples/ema_atr_strategy.html', plot_trades=True, open_browser=True)
    
    if is_send_single_email:
        # 发送邮件提醒
        subject = "单次回测完成提醒"
        body = f"单次回测已完成。胜率: {stats['Win Rate [%]']}%，交易数量: {stats['# Trades']}。"
        send_email_notification(subject, body)

