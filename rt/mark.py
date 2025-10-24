import talib

from utils import get_ohlcv_data

def ema_atr_filter(exchange, symbol, ema_period, atr_period, multiplier, atr_threshold_pct):
    try:
        # 获取K线数据
        df = get_ohlcv_data(exchange, symbol)
        
        # 计算技术指标
        df['ema'] = talib.EMA(df['close'], timeperiod=ema_period)
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=atr_period)
        df['upper_band'] = df['ema'] + (multiplier * df['atr'])
        df['lower_band'] = df['ema'] - (multiplier * df['atr'])
        
        atr_value = df['atr'].iloc[-1] # 获取ATR值

        # 获取最新价格数据
        current_close = df['close'].iloc[-1]
        previous_close = df['close'].iloc[-2]
        upper_band = df['upper_band'].iloc[-1]
        lower_band = df['lower_band'].iloc[-1]
        
        # 检查是否已有持仓
        positions = exchange.fetch_positions()
        has_position = any(pos['symbol'] == symbol and pos['contracts'] != 0 for pos in positions)
        if has_position:
            print("已有持仓，跳过开仓信号。")
            return None, atr_value
        
        # 波动率过滤器
        atr_pct = atr_value / current_close
        if atr_pct < atr_threshold_pct:
            print(f"波动率过低 ({atr_pct:.4f} < {atr_threshold_pct})，跳过交易。")
            return None, atr_value
        
        # 上轨突破条件
        upper_breakout = previous_close <= upper_band and current_close > upper_band
        
        # 下轨突破条件
        lower_breakout = previous_close >= lower_band and current_close < lower_band
        
        if upper_breakout:
            return 'upper_breakout', atr_value
        
        elif lower_breakout:
            return 'lower_breakout', atr_value
        
        return None, atr_value  # 无信号时也返回 atr_value
        
    except Exception as e:
        print(f"策略信号生成失败: {e}")
        return None, None