
## 项目描述
这是一个基于 Python 的量化交易回测项目，使用 backtesting 库对加密货币（主要是 BTC/USDT）15 分钟 K 线数据进行 EMA-ATR 趋势策略的回测。该策略通过 EMA（指数移动平均线）和 ATR（真实波动幅度均值）计算上下轨，当价格突破轨道时进行买卖操作，并设置基于 ATR 的止盈止损。系统支持单次回测和批量参数优化（使用 SAMBO 方法）。

## 功能特点
- EMA-ATR 策略实现，包含动态止盈止损
- 支持单次回测和批量参数优化
- 自定义优化指标（胜率与最小交易数量要求）
- 数据自动合并和预处理
- 可视化回测结果和参数热力图
- 交易记录导出和分析

## 安装

### 依赖项
1. 克隆或下载项目到本地
2. 安装主要依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 安装 TA-Lib（技术分析库，可能需要额外步骤）：
   - macOS: `brew install ta-lib`
   - Windows: 从[TA-Lib官网](http://ta-lib.org/hdr_dw.html)下载预编译库
   - Linux: `apt-get install ta-lib`

   然后执行：
   ```bash
   pip install TA-Lib
   ```

4. 如遇到 sambo 安装问题，可以尝试检查版本：
   ```bash
   python -c "import sambo; print(sambo.__version__)"
   ```
   并手动安装缺失依赖

## 数据准备
1. 准备 CSV 格式的 K 线数据，包含以下列：
   - `open_time`（毫秒级 Unix 时间戳）
   - `open`、`high`、`low`、`close`、`volume`
   
2. 将数据文件放置在 BTCUSDT-15m 目录下
   - 推荐按月份分割，例如 `BTCUSDT-15m-2024-01.csv`

3. 系统会自动合并数据文件生成 merged_BTCUSDT-15m.csv

## 使用方法

### 运行回测
1. 打开 ema_atr_trend.py，设置回测模式：
   - 单次回测：设置 `is_batch_test = False`
   - 批量优化：设置 `is_batch_test = True`（默认）
   
2. 调整策略参数（可选）：
   - `ema_period`：EMA 周期
   - `atr_period`：ATR 周期
   - `multiplier`：ATR 乘数

3. 运行脚本：
   ```bash
   python ema_atr_trend.py
   ```

### 查看结果
- 单次回测：
  - 控制台输出统计数据
  - 交易记录保存到 `result/trades.csv`
  - 回测可视化保存到 ema_atr_strategy.html
  
- 批量优化：
  - 参数热力图保存到 heatmap_ema_atr_strategy.html
  - 优化结果保存到 `result/heatmap_results48.csv`

## 文件结构
- ema_atr_trend.py: 主脚本，定义策略和回测逻辑
- utils.py: 工具函数，负责数据合并和加载
- data: 数据目录
  - `merged_BTCUSDT-15m.csv`: 合并后的数据文件
  - `BTCUSDT-15m/`: 原始分割数据
- result: 输出目录，存放交易记录
- examples: 示例输出目录，存放图表

## 优化说明
- 当前优化指标（`custom_maximize`）要求：
  - 最小交易数量：84
  - 最大化胜率（Win Rate）
- 优化参数范围：
  - `ema_period`: 2-202
  - `atr_period`: 10-100
  - `multiplier`: 0.5-1.0
- 可在 ema_atr_trend.py 文件中调整这些范围和目标

## 常见问题
- 如遇 sambo 依赖问题，请参考开发日记中的解决方案
- 批量优化参数空间大，可能耗时较长，可适当减少参数范围
- 默认使用 SAMBO 方法进行优化，比穷举法更高效

## 注意事项
- 该策略仅供学习和研究使用，实际交易请谨慎评估
- 回测结果不代表未来表现
- 推荐使用足够长的历史数据以获得更可靠的回测结果

## 许可证
MIT License