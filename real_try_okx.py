import os
import ccxt
import talib
import pandas as pd
import time

from datetime import datetime, timezone  # 添加 datetime 模块
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
ATR_THRESHOLD_PCT = 0.0098  # ATR波动率阈值百分比

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

def seek_mark():
    df = get_ohlcv_data(exchange)
    df = indicators(df)
    
    latest = df.iloc[-1]
    previous = df.iloc[-2]
    
    # 检查当前是否有仓位
    positions = exchange.fetch_positions()
    has_position = any(pos['symbol'] == SYMBOL and pos['contracts'] != 0 for pos in positions)
    
    # 检查ATR波动率过滤器（基于当前价格的百分比）
    # 如果ATR低于阈值百分比，不执行交易
    volatility_filter = latest['atr'] / latest['close'] > ATR_THRESHOLD_PCT
    
    # 多头入场信号：1. 第n-1根k线的收盘价 <= upper_band
    #                2. 第n根k线的收盘价 > upper_band
    #                3. 波动过滤器值 > 阈值
    #                4. 当前没有仓位
    if not has_position and previous['close'] <= previous['upper_band'] and latest['close'] > latest['upper_band'] and volatility_filter:
        return 'long_entry'
    
    # 空头入场信号：类似逻辑，1. 第n-1根k线的收盘价 >= lower_band
    #                2. 第n根k线的收盘价 < lower_band
    #                3. 波动过滤器值 > 阈值
    #                4. 当前没有仓位
    elif not has_position and previous['close'] >= previous['lower_band'] and latest['close'] < latest['lower_band'] and volatility_filter:
        return 'short_entry'
    
    else:
        return 'hold'

def strategy():  # 移除 is_long 参数，根据信号自动决定
    try:
        exchange.set_leverage(2, SYMBOL)  # 设置2倍杠杆
        
        # 获取信号
        signal = seek_mark()
        
        if signal == 'hold':
            print("无信号，跳过交易。")
            return
        
        # 获取ATR作为止损距离
        df = get_ohlcv_data(exchange)
        df = indicators(df)
        
        atr_value = df['atr'].iloc[-1]  # 最新ATR值
        sl_distance = atr_value  # 止损距离 = 1倍ATR
        tp_distance = sl_distance * RR  # 止盈距离 = 止损距离 * RR
        
        entry_price = None

        if signal == 'long_entry':
            # 做多逻辑
            order = exchange.create_market_buy_order(SYMBOL, 0.01)
            print("市价买入订单已提交:", order)
            
            time.sleep(2)
            filled_order = exchange.fetch_order(order['id'], SYMBOL)
            
            if filled_order and filled_order['status'] == 'closed' and filled_order['average']:
                entry_price = filled_order['average']
                print(f"订单已成交，实际入场价: {entry_price}")
            else:
                print("错误：无法获取订单成交价，取消设置止盈止损。")
                return

            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
            print(f"止损价格: {sl_price}, 止盈价格: {tp_price}")

            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market', 
                'sell', 
                0.01, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True}
            )
            print("止损订单（卖出）已设置:", sl_order)

            tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'sell', 0.01, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            print("止盈订单（卖出）已设置:", tp_order)
        
        elif signal == 'short_entry':
            # 做空逻辑
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

            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market', 
                'buy', 
                0.01, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True}
            )
            print("止损订单（买入）已设置:", sl_order)

            tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'buy', 0.01, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            print("止盈订单（买入）已设置:", tp_order)

    except Exception as e:
        print(f"策略执行失败: {e}")

def main():
    while True:  # 开始时间遍历，循环执行策略
        try:
            # 获取当前 UTC 时间
            now = datetime.now(timezone.utc)
            current_minute = now.minute
            
            # 计算当前分钟除以 15 的余数
            remainder = current_minute % 15
            
            # 计算需要等待的时间（分钟）
            wait_minutes = 0 if remainder == 0 else 15 - remainder
            
            # 转换为秒
            wait_seconds = wait_minutes * 60
            
            print(f"当前 UTC 时间: {now}, 分钟余数: {remainder}, 等待 {wait_minutes} 分钟 ({wait_seconds} 秒)")
            
            time.sleep(wait_seconds)
            
            strategy()  # 调用策略
            
            time.sleep(60)  # 每次调用策略后休息 60 秒
            
        except KeyboardInterrupt:
            print("用户中断，停止运行。")
            break
        except Exception as e:
            print(f"主循环错误: {e}")
            time.sleep(60)  # 出错后等待1分钟再试

if __name__ == "__main__":
    main()
