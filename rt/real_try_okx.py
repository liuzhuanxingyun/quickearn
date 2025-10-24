import os
import ccxt
import talib
import pandas as pd
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from utils import send_email_notification
from mark import ema_atr_filter

load_dotenv()

API_KEY = os.getenv('OKX_API_KEY')
API_SECRET = os.getenv('OKX_API_SECRET')
API_PASSPHRASE = os.getenv('OKX_API_PASSPHRASE')

EMAIL_TO = os.getenv('EMAIL_TO')
EMAIL_FROM = os.getenv('EMAIL_FROM')
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '1m'

EMA_PERIOD = 21
ATR_PERIOD = 10
MULTIPLIER = 4
ATR_THRESHOLD_PCT = 0.0007
RR = 1
FIXED_LEVERAGE = 10
RISK_USDT = 1

exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': API_PASSPHRASE,
    'enableRateLimit': True,
    'sandbox': False,
    'options': {
        'defaultType': 'swap',
        'marginMode': 'isolated',
    },
    'proxies': {
        'http': 'http://127.0.0.1:7897',  
        'https': 'http://127.0.0.1:7897',  
    }
})

# 添加一个时间段决定顺势逆势交易的函数
def time_checker(hour):
    if 4 <= hour <= 11:
        return 'counter_trend'
    elif 12 <= hour <= 23 or 0 <= hour <= 3:
        return 'trend_following'
    else:
        return 'trend_following'

def strategy():
    try:
        now = datetime.now(timezone.utc)
        hour = now.hour

        mark, atr_value = ema_atr_filter(exchange, SYMBOL, EMA_PERIOD, ATR_PERIOD, MULTIPLIER, ATR_THRESHOLD_PCT)

        strategy_type = time_checker(hour)  # 移到此处，确保始终定义

        signal = None
        # signal = 'long_entry'

        if mark:
            print(f"当前UTC小时: {hour}, 策略类型: {strategy_type}")
            
            # 根据策略类型调整信号
            if strategy_type == 'counter_trend':
                if mark == 'upper_breakout':
                    signal = 'short_entry'  # 逆势：上突破做空
                elif mark == 'lower_breakout':
                    signal = 'long_entry'   # 逆势：下突破做多
            elif strategy_type == 'trend_following':
                if mark == 'upper_breakout':
                    signal = 'long_entry'  # 顺势：上突破做多
                elif mark == 'lower_breakout':
                    signal = 'short_entry'  # 顺势：下突破做空
        
        if not signal:
            print("无交易信号。")
            return
        else:
            # 发送邮件通知
            subject = "交易信号触发"
            body = f"时间: {now}\n信号: {signal}\n策略类型: {strategy_type}\nATR值: {atr_value}"
            send_email_notification(subject, body)
            
            # 取消当前所有委托
            try:
                open_orders = exchange.fetch_open_orders(SYMBOL)
                if open_orders:
                    ids = [order['id'] for order in open_orders]
                    exchange.cancelOrders(ids, SYMBOL)
                    print("已取消当前所有委托。")
                else:
                    print("无开放委托。")
            except Exception as e:
                print(f"取消委托失败: {e}")
        
        sl_distance = atr_value
        tp_distance = sl_distance * RR

        size = RISK_USDT * 100 / sl_distance
        print(f"计算得张数: {size:.6f}")
        
        entry_price = None
        sl_order_id = None
        tp_order_id = None
        trailing_order_id = None

        if signal == 'long_entry':

            # 下单
            order = exchange.create_market_buy_order(SYMBOL, size, params={'posSide': 'long'})
            order_id = order['id']
            print(f"\033[92m市价买入订单已提交，订单ID: {order_id}\033[0m")  # 绿色标出
            time.sleep(1)
            filled_order = exchange.fetch_order(order_id, SYMBOL)
            if filled_order and filled_order['status'] == 'closed' and filled_order['average']:
                entry_price = filled_order['average']
                print(f"\033[92m订单已成交，实际入场价: {entry_price}\033[0m")  # 绿色标出
            else:
                print("错误：无法获取订单成交价，取消设置止盈止损。")
                return
            actual_size = float(filled_order.get('filled', filled_order.get('amount', size)))
            if actual_size <= 0:
                print("错误：成交张数为0，取消止损止盈设置。")
                return

            # 止盈止损
            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance
            print(f"止损价格: {sl_price}, 止盈价格: {tp_price}")
            # 设置止损订单
            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market', 
                'sell', 
                actual_size, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True, 'posSide': 'long'}
            )
            sl_order_id = sl_order['id']
            print(f"止损订单（卖出）已设置，订单ID: {sl_order_id}")
            # 设置止盈订单
            # tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'sell', actual_size, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            # tp_order_id = tp_order['id']
            # print(f"止盈订单（卖出）已设置，订单ID: {tp_order_id}")
            # 新增：设置移动止盈止损（trailing stop）
            trailing_order = exchange.create_order(
                SYMBOL,
                'trailing_stop',
                'sell',
                actual_size,
                params={
                    'callbackSpread': str(tp_distance),  # 回调幅度的价距
                    'activePx': str(tp_price),  # 激活价格为 tp_price
                    'reduceOnly': True,
                    'posSide': 'long'
                }
            )
            trailing_order_id = trailing_order['id']
            print(f"移动止盈止损订单（卖出）已设置，订单ID: {trailing_order_id}")
        
        elif signal == 'short_entry':

            # 下单
            order = exchange.create_market_sell_order(SYMBOL, size, params={'posSide': 'short'})
            order_id = order['id']
            print(f"\033[92m市价卖出订单已提交，订单ID: {order_id}\033[0m")  # 绿色标出
            time.sleep(1)
            filled_order = exchange.fetch_order(order_id, SYMBOL)
            if filled_order and filled_order['status'] == 'closed' and filled_order['average']:
                entry_price = filled_order['average']
                print(f"\033[92m订单已成交，实际入场价: {entry_price}\033[0m")  # 绿色标出
            else:
                print("错误：无法获取订单成交价，取消设置止盈止损。")
                return
            actual_size = float(filled_order.get('filled', filled_order.get('amount', size)))
            if actual_size <= 0:
                print("错误：成交张数为0，取消止损止盈设置。")
                return
            
            # 止盈止损
            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance
            print(f"止损价格: {sl_price}, 止盈价格: {tp_price}")
            # 设置止损订单
            sl_order = exchange.create_stop_loss_order(
                SYMBOL, 
                'market', 
                'buy', 
                actual_size, 
                stopLossPrice=sl_price, 
                params={'reduceOnly': True, 'posSide': 'short'}
            )
            sl_order_id = sl_order['id']
            print(f"止损订单（买入）已设置，订单ID: {sl_order_id}")
            # 设置止盈订单
            # tp_order = exchange.create_take_profit_order(SYMBOL, 'limit', 'buy', actual_size, price=tp_price, takeProfitPrice=(entry_price + tp_price) / 2, params={'reduceOnly': True})
            # tp_order_id = tp_order['id']
            # print(f"止盈订单（买入）已设置，订单ID: {tp_order_id}")
            # 新增：设置移动止盈止损（trailing stop）
            trailing_order = exchange.create_order(
                SYMBOL,
                'trailing_stop',
                'buy',
                actual_size,
                params={
                    'callbackSpread': str(tp_distance),  # 回调幅度的价距
                    'activePx': str(tp_price),  # 激活价格为 tp_price
                    'reduceOnly': True,
                    'posSide': 'short'
                }
            )
            trailing_order_id = trailing_order['id']
            print(f"移动止盈止损订单（买入）已设置，订单ID: {trailing_order_id}")
  
    except Exception as e:
        print(f"策略执行失败: {e}")

def main():
    try:
        balance = exchange.fetch_balance()
        print("API连接成功，余额:", balance['total']['USDT'])

        leverage_to_set = int(FIXED_LEVERAGE)
        # 分别设置多头和空头杠杆
        exchange.set_leverage(leverage_to_set, SYMBOL, {'mgnMode': 'isolated', 'posSide': 'long'})
        exchange.set_leverage(leverage_to_set, SYMBOL, {'mgnMode': 'isolated', 'posSide': 'short'})
        print(f"当前杠杆为：{leverage_to_set}（多头和空头均设置）")

    except Exception as e:
        print(f"API连接失败: {e}")
    
    while True:
        try: 
            strategy()  # 调用策略
            print("-" * 50)
            # 分钟级别以上可以用这个办法
            # now = datetime.now(timezone.utc)
            # wait_seconds = (15 - (now.minute % 15)) * 60 - now.second
            # print(f"等待 {wait_seconds} 秒到下一个15分钟整点")
            # time.sleep(wait_seconds)
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("用户中断，停止运行。")
            break
        except Exception as e:
            print(f"主循环错误: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()



