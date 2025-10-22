import os
import ccxt
import talib
import pandas as pd
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('OKX_API_KEY')
API_SECRET = os.getenv('OKX_API_SECRET')
API_PASSPHRASE = os.getenv('OKX_API_PASSPHRASE')

FIXED_LEVERAGE = float(os.getenv('FIXED_LEVERAGE'))
RISK_USDT = float(os.getenv('RISK_USDT'))

SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '1m'

EMA_PERIOD = 13
ATR_PERIOD = 14
MULTIPLIER = 1
ATR_THRESHOLD_PCT = 0
RR = 1

exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': API_PASSPHRASE,
    'enableRateLimit': True,
    'sandbox': True,
    'options': {
        'defaultType': 'swap',
        'marginMode': 'isolated',
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
    df['upper_band'] = df['ema'] + (MULTIPLIER * df['atr'])
    df['lower_band'] = df['ema'] - (MULTIPLIER * df['atr'])
    return df

def seek_mark():
    df = get_ohlcv_data(exchange)
    df = indicators(df)
    
    latest = df.iloc[-1]
    previous = df.iloc[-2]
    
    positions = exchange.fetch_positions()
    has_position = any(pos['symbol'] == SYMBOL and pos['contracts'] != 0 for pos in positions)
    
    volatility_filter = latest['atr'] / latest['close'] > ATR_THRESHOLD_PCT
    
    if not has_position and previous['close'] <= previous['upper_band'] and latest['close'] > latest['upper_band'] and volatility_filter:
        return 'long_entry'
    
    elif not has_position and previous['close'] >= previous['lower_band'] and latest['close'] < latest['lower_band'] and volatility_filter:
        return 'short_entry'
    
    else:
        return 'hold'  

def strategy():
    try:
        # seek_mark() 返回交易信号
        signal = seek_mark()
        
        if signal == 'hold':
            print("无信号，跳过交易。")
            return
        
        df = get_ohlcv_data(exchange)
        df = indicators(df)

        atr_value = df['atr'].iloc[-1]
        sl_distance = atr_value
        tp_distance = sl_distance * RR
        
        size = 10 * RISK_USDT * FIXED_LEVERAGE / sl_distance
        print(f"计算得张数: {size:.6f}")
        
        entry_price = None
        sl_order_id = None
        tp_order_id = None

        if signal == 'long_entry':
            order = exchange.create_market_buy_order(SYMBOL, size)
            order_id = order['id']
            print(f"市价买入订单已提交，订单ID: {order_id}")
            
            time.sleep(1)
            filled_order = exchange.fetch_order(order_id, SYMBOL)
            
            if filled_order and filled_order['status'] == 'closed' and filled_order['average']:
                entry_price = filled_order['average']
                print(f"订单已成交，实际入场价: {entry_price}")
            else:
                print("错误：无法获取订单成交价，取消设置止盈止损。")
                return

            actual_size = float(filled_order.get('filled', filled_order.get('amount', size)))
            if actual_size <= 0:
                print("错误：成交张数为0，取消止损止盈设置。")
                return

            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
            print(f"止损价格: {sl_price}, 止盈价格: {tp_price}")

            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market', 
                'sell', 
                actual_size, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True}
            )
            sl_order_id = sl_order['id']
            print(f"止损订单（卖出）已设置，订单ID: {sl_order_id}")

            tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'sell', actual_size, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            tp_order_id = tp_order['id']
            print(f"止盈订单（卖出）已设置，订单ID: {tp_order_id}")
        
        elif signal == 'short_entry':
            order = exchange.create_market_sell_order(SYMBOL, size)
            order_id = order['id']
            print(f"市价卖出订单已提交，订单ID: {order_id}")
            is_long = False

            time.sleep(2)
            filled_order = exchange.fetch_order(order_id, SYMBOL)

            if filled_order and filled_order['status'] == 'closed' and filled_order['average']:
                entry_price = filled_order['average']
                print(f"订单已成交，实际入场价: {entry_price}")
            else:
                print("错误：无法获取订单成交价，取消设置止盈止损。")
                return

            actual_size = float(filled_order.get('filled', filled_order.get('amount', size)))
            if actual_size <= 0:
                print("错误：成交张数为0，取消止损止盈设置。")
                return

            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance
            print(f"止损价格: {sl_price}, 止盈价格: {tp_price}")

            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market', 
                'buy', 
                actual_size, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True}
            )
            sl_order_id = sl_order['id']
            print(f"止损订单（买入）已设置，订单ID: {sl_order_id}")

            tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'buy', actual_size, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            tp_order_id = tp_order['id']
            print(f"止盈订单（买入）已设置，订单ID: {tp_order_id}")
  
    except Exception as e:
        print(f"策略执行失败: {e}")

def main():
    try:
        balance = exchange.fetch_balance()
        print("API连接成功，余额:", balance['total']['USDT'])

        leverage_to_set = int(FIXED_LEVERAGE)
        exchange.set_leverage(leverage_to_set, SYMBOL, {'mgnMode': 'isolated'})
        print(f"当前杠杆为：{leverage_to_set}")

    except Exception as e:
        print(f"API连接失败: {e}")
    
    while True:
        try: 
            strategy()  # 调用策略
            
            time.sleep(60)  # 每次调用策略后休息 60 秒
            
        except KeyboardInterrupt:
            print("用户中断，停止运行。")
            break
        except Exception as e:
            print(f"主循环错误: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()



            # 简化对齐逻辑
            # now = datetime.now(timezone.utc)
            # wait_seconds = (15 - (now.minute % 15)) * 60 - now.second
            # print(f"等待 {wait_seconds} 秒到下一个15分钟整点")
            # time.sleep(wait_seconds)