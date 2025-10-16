import pandas as pd
import talib
import numpy as np
import os

from datetime import datetime
from backtesting import Backtest, Strategy
from backtesting.lib import crossover, plot_heatmaps
from utils import load_and_process_data, merge_csv_files, send_email_notification, download_binance_data, unzip_binance_data

def custom_maximize(stats):
    # 检查交易数量和胜率有效性
    if (stats['# Trades'] < 84 or
        pd.isna(stats['Win Rate [%]'])):
        return 0
    # 直接返回胜率（百分比形式）
    return stats['Win Rate [%]']

# 设置开关
is_download_data = False  # 是否下载数据
is_batch_test = False  # 是否进行批量回测
is_send_batch_email = True  # 批量回测邮件开关
is_send_single_email = False  # 单次回测邮件开关

if is_download_data:
    download_binance_data(symbol='BTCUSDT', interval='15m', years=[2022], months=range(1, 13), save_dir='./data')
    unzip_binance_data(symbol='BTCUSDT', interval='15m', save_dir='./data')  # 添加解压调用
    merged_data = merge_csv_files(symbol='BTCUSDT', interval='15m')

data = load_and_process_data('data/merged_BTCUSDT-15m.csv')
# data/ETHUSDT-15m/ETHUSDT-15m-2025-01.csv
# data/BTCUSDT-15m/BTCUSDT-15m-2025-09.csv
# 测试用

print(data.head())

class EmaAtrStrategy(Strategy):
    ema_period = 135
    atr_period = 6
    multiplier = 9
    atr_threshold_pct = 0.004  # ATR波动率过滤器阈值（百分比，基于当前价格）
    rr = 2.0  # 风险回报比：止盈距离 = 止损距离 * rr

    def init(self):
        price = self.data.Close
        self.ema = self.I(talib.EMA, price, timeperiod=self.ema_period)
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=self.atr_period)

    def next(self):
        # 检查ATR波动率过滤器（基于当前价格的百分比）
        if self.atr[-1] / self.data.Close[-1] < self.atr_threshold_pct:
            return  # 如果ATR低于阈值百分比，不执行交易
        
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

bt = Backtest(data, EmaAtrStrategy, cash=1_000_000_000, commission=0.0005)  

if is_batch_test:
    # 定义优化参数
    ema_period_range = range(55, 155, 20)
    atr_period_range = np.arange(6, 16, 2)
    multiplier_range = list(np.arange(0.05, 10.05, 1))
    atr_threshold_pct_range = list(np.arange(0, 0.01, 0.002))  # ATR阈值百分比范围
    rr_range = [1]
    
    # 自动计算组合总数
    total_combinations = (len(ema_period_range) * len(atr_period_range) * 
                          len(multiplier_range) * len(atr_threshold_pct_range) * len(rr_range))
    print(f"优化参数组合总数: {total_combinations}")

    stats, heatmap= bt.optimize(
        ema_period=ema_period_range,
        atr_period=atr_period_range,
        multiplier=multiplier_range,
        atr_threshold_pct=atr_threshold_pct_range,  # 调整ATR阈值百分比范围
        rr=rr_range,  # 新增rr优化参数
        max_tries=1000,
        method='sambo', 
        # return_optimization=True,
        return_heatmap=True,

        # maximize='Win Rate [%]'
        maximize=custom_maximize
    )
    print(heatmap)
    # 生成时间戳并创建新文件夹
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_folder = f"result/batch_{timestamp}"
    os.makedirs(batch_folder, exist_ok=True)
    
    # 修改文件名以包含最佳胜率和交易数量
    win_rate = stats['Win Rate [%]']
    num_trades = stats['# Trades']
    heatmap_filename = f'{batch_folder}/heatmap_win{win_rate}_trades{num_trades}.csv'
    plot_filename = f'{batch_folder}/heatmap_win{win_rate}_trades{num_trades}.html'
    plot_heatmaps(heatmap, filename=plot_filename, open_browser=True)
    heatmap.to_csv(heatmap_filename, index=True)
    
    if is_send_batch_email:
        # 发送邮件提醒
        subject = "批量回测完成提醒"
        body = f"批量回测已完成。最佳胜率: {win_rate}%，交易数量: {num_trades}。"
        send_email_notification(subject, body)

else:

    stats = bt.run()
    print(stats)
    print(stats._trades)
    # 生成时间戳并创建新文件夹
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    single_folder = f"result/single_{timestamp}"
    os.makedirs(single_folder, exist_ok=True)
    
    # 修改文件名以包含胜率和交易数量
    win_rate = stats['Win Rate [%]']
    num_trades = stats['# Trades']
    trades_filename = f'{single_folder}/trades_win{win_rate}_trades{num_trades}.csv'
    plot_filename = f'{single_folder}/ema_atr_win{win_rate}_trades{num_trades}.html'
    stats._trades.to_csv(trades_filename, index=True)
    bt.plot(filename=plot_filename, plot_trades=True, open_browser=True)
    
    if is_send_single_email:
        # 发送邮件提醒
        subject = "单次回测完成提醒"
        body = f"单次回测已完成。胜率: {win_rate}%，交易数量: {num_trades}。"
        send_email_notification(subject, body)

