# 01exchange Grid Trading Bot

基于01.xyz去中心化交易所的BTC网格自动交易系统，包含完整的风控机制、动态仓位管理和RSI/ADX指标判断。

## ✨ 核心特性

- **滑动窗口网格策略**: 18单固定窗口，围绕中间价±12%自动布局
- **动态仓位管理**: 根据持仓自动调整买卖比例，最大15倍保护
- **智能风控系统**: 基于RSI/ADX指标判断市场状态，强趋势时自动触发15分钟冷却
- **本地订单跟踪**: 解决01exchange无订单查询API的问题
- **自动会话续期**: Session过期自动重建，无需手动干预
- **完整日志记录**: 所有操作详细记录，便于调试和分析

## 📋 目录结构

```
01exchange-grid-bot/
├── config/                  # 配置模块
│   ├── __init__.py
│   └── settings.py         # 统一配置管理
├── src/                    # 核心代码
│   ├── __init__.py
│   ├── api_client.py       # 01exchange API客户端
│   ├── indicators.py       # 技术指标计算（RSI/ADX）
│   ├── order_tracker.py    # 本地订单跟踪
│   ├── risk_manager.py     # 风控管理器
│   ├── grid_strategy.py    # 网格策略核心
│   └── trader.py           # 主交易循环
├── main.py                 # 启动入口
├── requirements.txt        # Python依赖
├── .env.example           # 环境变量示例
├── .gitignore
└── README.md
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Solana钱包（需要有私钥）
- VPS或本地运行环境

### 2. 安装依赖

```bash
# 克隆仓库
git clone https://github.com/yourusername/01exchange-grid-bot.git
cd 01exchange-grid-bot

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 下载并编译Protobuf Schema

```bash
# 下载schema文件
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto

# 编译为Python
protoc --python_out=. schema.proto
```

编译后会生成 `schema_pb2.py` 文件。

### 4. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件
nano .env  # 或使用其他编辑器
```

**重要配置项**：

```ini
# API地址（主网/测试网）
API_URL=https://zo-mainnet.n1.xyz

# Solana钱包私钥（Base58格式）
SOLANA_PRIVATE_KEY=your_private_key_here

# 交易配置
SYMBOL=BTCUSD
MARKET_ID=0

# 网格策略参数
TOTAL_ORDERS=18              # 总订单数
WINDOW_PERCENT=0.12          # 窗口宽度12%
SELL_RATIO=0.5              # 卖单比例50%
BUY_RATIO=0.5               # 买单比例50%
BASE_PRICE_INTERVAL=10      # 价格间距$10
MAX_MULTIPLIER=15           # 最大开仓倍数

# 风控参数
RSI_MIN=30                  # RSI下限
RSI_MAX=70                  # RSI上限
ADX_TREND_THRESHOLD=25      # ADX趋势阈值
ADX_STRONG_TREND=30         # ADX强趋势阈值
RISK_COOLDOWN_MINUTES=15    # 风控冷却15分钟
```

### 5. 运行程序

```bash
python main.py
```

## 📊 策略详解

### 滑动窗口网格

```
价格分布示例（窗口12%，中间价$70,000）:

窗口上界: $78,400 (+12%)
        ↑
    卖单9: $78,000
    卖单8: $77,990
    ...
    卖单1: $70,020 (卖一价 + 安全间隙)
    ────────────────────
    中间价: $70,000
    ────────────────────
    买单1: $69,980 (买一价 - 安全间隙)
    ...
    买单8: $69,020
    买单9: $69,010
        ↓
窗口下界: $61,600 (-12%)
```

### 动态仓位管理

```python
持仓倍数 = |当前仓位BTC| / 开仓大小

if 持仓倍数 >= 15:
    # 达到上限，停止对应方向
    if 多单过多: 只开卖单 (卖单100%, 买单0%)
    if 空单过多: 只开买单 (买单100%, 卖单0%)
elif 持仓倍数 > 0:
    # 动态调整比例
    减少比例 = 持仓倍数 / 15
    if 多单过多: 减少买单比例
    if 空单过多: 减少卖单比例
else:
    # 无持仓，使用默认50/50
```

### 风控机制

**市场类型判断**：

1. **强趋势市场** (ADX > 30)
   - 🛑 触发15分钟风控冷却
   - 立即平仓所有持仓
   - 取消所有挂单

2. **中等趋势市场** (ADX > 25)
   - ⚠️ 警告但允许交易
   - 如果RSI过于极端（< 25 或 > 75）则触发风控
   - 否则继续谨慎执行

3. **震荡市场** (ADX < 25)
   - ✅ 最适合网格交易
   - 检查RSI是否在30-70区间
   - 不在区间则触发风控

**冷却机制**：

- 触发后15分钟内不执行新交易
- 期间每10秒检查一次状态
- 定期平仓和撤单
- 到时间后自动恢复

## 🔧 参数调优建议

### 保守型（适合新手）

```ini
TOTAL_ORDERS=12
WINDOW_PERCENT=0.08
BASE_PRICE_INTERVAL=15
MAX_MULTIPLIER=10
RSI_MIN=35
RSI_MAX=65
```

### 激进型（经验丰富）

```ini
TOTAL_ORDERS=24
WINDOW_PERCENT=0.15
BASE_PRICE_INTERVAL=8
MAX_MULTIPLIER=20
RSI_MIN=25
RSI_MAX=75
```

### 窗口宽度选择

| 波动率 | 建议窗口 | 说明 |
|--------|---------|------|
| 低波动 | 0.08-0.10 | 价格稳定，窄窗口 |
| 中波动 | 0.10-0.12 | 正常行情 |
| 高波动 | 0.12-0.18 | 剧烈波动，宽窗口 |

## 📈 监控与日志

### 日志级别

```ini
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### 日志文件

- `grid_trader.log`: 所有日志记录
- 控制台：实时输出

### 关键日志示例

```
2026-02-01 10:30:15 [INFO] trader: ==========================================
2026-02-01 10:30:15 [INFO] trader: 第 42 次循环 - 10:30:15
2026-02-01 10:30:15 [INFO] trader: ==========================================
2026-02-01 10:30:16 [INFO] trader: 📊 当前指标 - RSI: 45.23, ADX: 18.56
2026-02-01 10:30:16 [INFO] trader: ✅ 震荡市场且RSI在区间内
2026-02-01 10:30:17 [INFO] trader: 💰 价格 - 买一: $69,995, 卖一: $70,005, 中间: $70,000
2026-02-01 10:30:18 [INFO] grid_strategy: 中间价 $70000.0 | 窗口 ±$4200
2026-02-01 10:30:18 [INFO] grid_strategy: 当前订单: 9卖 + 9买 = 18
2026-02-01 10:30:18 [INFO] grid_strategy: 需下单: 2卖 + 1买
2026-02-01 10:30:20 [INFO] api_client: ✅ 下单成功: sell 0.001 @ $70100.0 (ID: 12345)
```

## ⚠️ 风险提示

1. **资金风险**: 使用前请在测试网充分测试
2. **市场风险**: 单边行情可能导致大量浮亏
3. **技术风险**: API故障、网络中断等
4. **仓位控制**: 建议初始仓位不超过总资金的30%
5. **监控重要**: 定期检查运行状态和持仓

## 🛠️ 故障排除

### 问题1: schema_pb2 not found

```bash
# 解决方案：重新编译protobuf
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto
protoc --python_out=. schema.proto
```

### 问题2: Invalid private key

```bash
# 检查私钥格式，应该是Base58编码
# 可以用solana-keygen工具生成：
solana-keygen new --outfile ~/my-keypair.json
```

### 问题3: Session过期频繁

- 检查系统时间是否正确
- 检查网络连接稳定性
- Session会自动续期，无需手动处理

### 问题4: 无法获取指标数据

- 检查网络是否能访问Binance
- 可以切换其他交易所：`exchange_id='okx'`
- 或实现自己的指标计算

## 📝 开发说明

### 添加新交易所支持

修改 `src/indicators.py`:

```python
# 使用OKX获取K线
calc = IndicatorCalculator('okx')
```

### 自定义策略

继承 `GridStrategy` 类：

```python
from src.grid_strategy import GridStrategy

class MyCustomStrategy(GridStrategy):
    def calculate_grid_prices(self, ...):
        # 自定义逻辑
        pass
```

### 添加新指标

在 `src/indicators.py` 中添加计算方法：

```python
@staticmethod
def calculate_macd(prices, fast=12, slow=26, signal=9):
    # MACD计算逻辑
    pass
```

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 License

MIT License

## 🙏 致谢

- 原始JS脚本作者: [@ddazmon](https://twitter.com/ddazmon)
- 01exchange官方文档
- Python开源社区

## 📧 联系方式

- GitHub Issues: [提交问题](https://github.com/yourusername/01exchange-grid-bot/issues)
- Twitter: [@your_twitter](https://twitter.com/your_twitter)

---

**免责声明**: 本项目仅供学习和研究使用，使用本程序交易产生的任何损失由使用者自行承担。请谨慎评估风险后使用。

**风险警告**: 加密货币交易具有高风险，可能导致本金损失。请确保您完全理解风险后再使用本程序。
