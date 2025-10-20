import os
import ccxt
import talib
import pandas as pd
import time # 导入 time 模块

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('OKX_API_KEY')
API_SECRET = os.getenv('OKX_API_SECRET')
API_PASSPHRASE = os.getenv('OKX_API_PASSPHRASE')

SYMBOL = 'BTC/USDT:USDT'  # 交易对
TIMEFRAME = '15m'    # 时间帧

EMA_PERIOD = 51  # EMA周期
ATR_PERIOD = 3   # ATR周期
MULTIPLIER = 2   # ATR倍数，用于计算轨道
RR = 2.0  # 风险回报比

exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': API_PASSPHRASE,
    'enableRateLimit': True,  # 启用速率限制，避免API调用过频
    'sandbox': True,  # 启用模拟账户
    'options': {
        'defaultType': 'swap',  # 默认交易类型为永续合约
        'marginMode': 'isolated', # 逐仓模式
    },
    'proxies': {
        'http': 'http://127.0.0.1:7897',  
        'https': 'http://127.0.0.1:7897',  
    }
})

def get_ohlcv_data(exchange, symbol=SYMBOL, timeframe=TIMEFRAME, limit=100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def indicators(df):
    df['ema'] = talib.EMA(df['close'], timeperiod=EMA_PERIOD)
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=ATR_PERIOD)
    df['upper_band'] = df['ema'] + (MULTIPLIER * df['atr'])  # 上轨道
    df['lower_band'] = df['ema'] - (MULTIPLIER * df['atr'])  # 下轨道
    return df

def strategy(is_long=False):  # 添加布尔值参数，False=做空，True=做多
    try:
        exchange.set_leverage(2, SYMBOL)  # 设置2倍杠杆
        
        # 获取ATR作为止损距离
        df = get_ohlcv_data(exchange)
        df = indicators(df)
        
        atr_value = df['atr'].iloc[-1]  # 最新ATR值
        sl_distance = atr_value  # 止损距离 = 1倍ATR
        tp_distance = sl_distance * RR  # 止盈距离 = 止损距离 * RR
        
        entry_price = None

        if is_long:
            # 1. 先下市价单
            order = exchange.create_market_buy_order(SYMBOL, 0.01)
            print("市价买入订单已提交:", order)
            
            # 2. 等待订单成交并获取实际成交价
            time.sleep(2) # 等待2秒，确保订单有足够时间成交
            filled_order = exchange.fetch_order(order['id'], SYMBOL)
            
            if filled_order and filled_order['status'] == 'closed' and filled_order['average']:
                entry_price = filled_order['average']
                print(f"订单已成交，实际入场价: {entry_price}")
            else:
                print("错误：无法获取订单成交价，取消设置止盈止损。")
                # 此处可以添加逻辑，比如取消未成交的订单
                return

            # 3. 使用实际成交价计算并设置止盈止损
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
            print(f"止损价格: {sl_price}, 止盈价格: {tp_price}")

            # --- 核心修改：将止损改为限价单 ---
            # 创建一个“止损限价平仓”订单
            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market',  # <--- 修改为 'limit'
                'sell', 
                0.01, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True}
            )
            print("止损订单（卖出）已设置:", sl_order)

            # 创建一个“限价止盈平仓”订单
            tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'sell', 0.01, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            print("止盈订单（卖出）已设置:", tp_order)
        else:
            # 做空逻辑类似
            order = exchange.create_market_sell_order(SYMBOL, 0.01)
            print("市价卖出订单已提交:", order)

            time.sleep(2)
            filled_order = exchange.fetch_order(order['id'], SYMBOL)

            if filled_order and filled_order['status'] == 'closed' and filled_order['average']:
                entry_price = filled_order['average']
                print(f"订单已成交，实际入场价: {entry_price}")
            else:
                print("错误：无法获取订单成交价，取消设置止盈止损。")
                return

            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance
            print(f"止损价格: {sl_price}, 止盈价格: {tp_price}")

            # --- 核心修改：将止损改为限价单 ---
            # 创建一个“止损限价平仓”订单
            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market',  # <--- 修改为 'limit'
                'buy', 
                0.01, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True}
            )
            print("止损订单（买入）已设置:", sl_order)

            # 创建一个“限价止盈平仓”订单
            tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'buy', 0.01, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            print("止盈订单（买入）已设置:", tp_order)

    except Exception as e:
        print(f"策略执行失败: {e}")

def main():
    strategy(is_long=True)  # 调用策略，默认做多

if __name__ == "__main__":
    main()
