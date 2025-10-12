import pandas as pd
import talib
import numpy as np

from backtesting import Backtest, Strategy
from backtesting.lib import crossover, FractionalBacktest, plot_heatmaps
from utils import load_and_process_data, merge_csv_files

def custom_maximize(stats):
    # 检查交易数量和胜率有效性
    if (stats['# Trades'] < 84 or
        pd.isna(stats['Win Rate [%]'])):
        return 0
    # 直接返回胜率（百分比形式）
    return stats['Win Rate [%]']

merged_data = merge_csv_files()
data = load_and_process_data()
# data/BTCUSDT-15m/BTCUSDT-15m-2025-09.csv
# 测试用

print(data.head())

class EmaAtrStrategy(Strategy):
    ema_period = 2
    atr_period = 10
    multiplier = 0.71

    def init(self):
        price = self.data.Close
        self.ema = self.I(talib.EMA, price, timeperiod=self.ema_period)
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, timeperiod=self.atr_period)

    def next(self):
        upper = self.ema + self.atr * self.multiplier
        lower = self.ema - self.atr * self.multiplier
        if crossover(self.data.Close, upper):
            self.position.close()
            self.buy(tp=self.data.Close+self.atr, sl=self.data.Close-self.atr)
        elif crossover(lower, self.data.Close):
            self.position.close()
            self.sell(tp=self.data.Close-self.atr, sl=self.data.Close+self.atr)

bt = FractionalBacktest(data, EmaAtrStrategy, cash=10_000)

is_batch_test = False

if is_batch_test:

    stats, heatmap= bt.optimize(
        ema_period=range(2, 202, 1),
        atr_period=np.arange(10, 100, 1),
        multiplier=list(np.arange(0.5, 1, 0.1)),
        max_tries=100000,
        method='sambo', 
        # return_optimization=True,
        return_heatmap=True,

        # maximize='Win Rate [%]'
        maximize=custom_maximize
    )
    print(heatmap)
    plot_heatmaps(heatmap, filename='examples/heatmap_ema_atr_strategy.html', open_browser=True)
    heatmap.to_csv('result/heatmap_results48.csv', index=True)

else:

    stats = bt.run()
    print(stats)
    print(stats._trades)
    stats._trades.to_csv('result/trades.csv', index=True)
    bt.plot(filename='examples/ema_atr_strategy.html', plot_trades=True, open_browser=True)

