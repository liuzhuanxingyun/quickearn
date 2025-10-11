import pandas as pd
import talib
import numpy as np

from backtesting import Backtest, Strategy
from backtesting.lib import crossover, FractionalBacktest
from utils import load_and_process_data, merge_csv_files

merged_data = merge_csv_files()
data = load_and_process_data(file_path='data/BTCUSDT-15m/BTCUSDT-15m-2025-09.csv')

print(data.head())

class EmaAtrStrategy(Strategy):
    ema_period = 12
    atr_period = 14
    multiplier = 3.3

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

is_batch_test = True

if is_batch_test:
    stats, heatmap = bt.optimize(
        ema_period=range(10, 50, 2),
        atr_period=range(10, 30, 2),
        multiplier=list(np.arange(1.0, 10, 0.1)),
        max_tries=10,
        method='sambo', 
        # return_optimization=True,
        return_heatmap=True,
        # maximize='Equity Final [$]',
        # constraint=lambda ema_period, atr_period, multiplier: atr_period < ema_period
    )
    print(heatmap)
else:
    stats = bt.run()
    print(stats)
    print(stats._trades)
    stats._trades.to_csv('result/trades.csv', index=False)

# bt.plot(filename='examples/ema_atr_strategy.html', plot_trades=True, open_browser=True)
