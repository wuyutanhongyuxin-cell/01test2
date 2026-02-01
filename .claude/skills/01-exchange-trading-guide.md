# 01exchange Grid Trading Bot 开发完整指南

## 版本信息
- **版本**: v2.1
- **更新日期**: 2026-02-01
- **项目地址**: https://github.com/wuyutanhongyuxin-cell/01test2

---

## 一、核心技术要点

### 1.1 Protobuf签名验证机制

**关键发现**：签名必须包含varint长度前缀

```python
# ❌ 错误方式
payload = action.SerializeToString()
signature = sign_func(payload)  # 只签名payload

# ✅ 正确方式
payload = action.SerializeToString()
length_prefix = encode_varint(len(payload))
message = length_prefix + payload  # 组合完整消息
signature = sign_func(message)     # 签名完整消息（包含长度前缀）
final_data = message + signature   # 发送数据
```

**双签名机制**：
- **User Sign**（CreateSession用）：`sign_message(hexlify(message))`
- **Session Sign**（PlaceOrder/CancelOrder用）：`sign_message(message)`

### 1.2 Response解析

响应数据也包含varint长度前缀，必须先解码：

```python
async def _execute_action(self, action, keypair, sign_func):
    # ... 发送请求 ...
    response_data = await resp.read()

    # 解码varint长度前缀
    msg_len, pos = self._decode_varint(response_data, 0)
    actual_data = response_data[pos:pos + msg_len]

    # 解析Receipt
    receipt = schema_pb2.Receipt()
    receipt.ParseFromString(actual_data)
    return receipt
```

### 1.3 Varint编解码实现

```python
def _encode_varint(self, value: int) -> bytes:
    """编码Varint"""
    buf = bytearray()
    while value >= 0x80:
        buf.append((value & 0x7f) | 0x80)
        value >>= 7
    buf.append(value)
    return bytes(buf)

def _decode_varint(self, data: bytes, offset: int = 0):
    """解码Varint并返回(值, 消耗的字节数)"""
    shift = 0
    result = 0
    while True:
        byte = data[offset]
        result |= (byte & 0x7f) << shift
        offset += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, offset
```

---

## 二、技术指标计算

### 2.1 ADX指标计算修复（重要！）

**问题**：使用简单移动平均(SMA)导致ADX值偏高

**症状**：
- 程序计算：ADX=36.59
- UI显示：ADX=18.61
- 导致错误触发强趋势风控

**原因**：
标准ADX应使用Wilder's Smoothing方法（一种特殊的EMA），而非SMA。

**修复方案**：

```python
@staticmethod
def calculate_adx(high, low, close, period=14):
    """标准ADX计算 - 使用Wilder's Smoothing"""

    # 1. 计算TR, +DM, -DM
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0))
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0))

    # 2. Wilder's Smoothing (alpha=1/period)
    # span = 2*period - 1 等价于 alpha=1/period
    wilder_span = 2 * period - 1

    atr = tr.ewm(span=wilder_span, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(span=wilder_span, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(span=wilder_span, adjust=False).mean()

    # 3. 计算DI
    plus_di = 100 * plus_dm_smooth / atr
    minus_di = 100 * minus_dm_smooth / atr

    # 4. 计算DX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)

    # 5. 对DX使用Wilder's Smoothing得到ADX
    adx = dx.ewm(span=wilder_span, adjust=False).mean()

    return float(adx.iloc[-1])
```

**测试结果**：
- 修复前：ADX=36.59（错误）
- 修复后：ADX=19.04（正确，接近UI的18.61）

### 2.2 数据源配置

当前使用Binance作为K线数据源：

```python
# src/indicators.py
calc = IndicatorCalculator('binance')
indicators = await calc.get_indicators('BTC/USDT', '5m')
```

**配置参数**（在.env中）：
- `INDICATOR_SYMBOL=BTC/USDT` - 交易对
- `INDICATOR_TIMEFRAME=5m` - K线周期

---

## 三、本地订单跟踪机制

**背景**：01exchange没有提供订单查询API

**解决方案**：实现本地订单状态管理

```python
# src/order_tracker.py
class OrderTracker:
    def __init__(self):
        self.active_orders: Dict[int, Order] = {}  # order_id -> Order
        self.order_history: List[Order] = []

    def add_order(self, order: Order):
        """添加新订单"""
        self.active_orders[order.order_id] = order

    def remove_order(self, order_id: int):
        """移除订单（已成交/已取消）"""
        if order_id in self.active_orders:
            order = self.active_orders.pop(order_id)
            self.order_history.append(order)

    def find_order_by_price(self, price: float, side: str):
        """根据价格和方向查找订单"""
        for order in self.active_orders.values():
            if order.side == side and abs(order.price - price) < 0.01:
                return order
        return None
```

**使用场景**：
- 下单后立即记录到tracker
- 撤单时通过价格查找order_id
- 检查订单是否仍然活跃

---

## 四、网格策略实现

### 4.1 滑动窗口计算

```python
# 18单网格，窗口范围：中间价 ± 12%
TOTAL_ORDERS = 18
WINDOW_PERCENT = 0.12

mid_price = (best_bid + best_ask) / 2
window_size = mid_price * WINDOW_PERCENT
lower_bound = mid_price - window_size  # -12%
upper_bound = mid_price + window_size  # +12%
```

### 4.2 动态仓位管理

```python
def calculate_buy_sell_ratio(position: float, open_size: float, max_multiplier: int = 15):
    """根据持仓动态调整买卖比例"""

    multiplier = abs(position) / open_size

    if multiplier >= max_multiplier:
        # 达到最大倍数，只允许反向开仓
        if position > 0:
            return 1.0, 0.0  # 100%卖单，0%买单
        else:
            return 0.0, 1.0  # 0%卖单，100%买单
    else:
        # 动态调整
        reduce_ratio = multiplier / max_multiplier

        if position > 0:  # 持有多仓
            buy_ratio = 0.5 * (1 - reduce_ratio)
            sell_ratio = 0.5 * (1 + reduce_ratio)
        else:  # 持有空仓
            buy_ratio = 0.5 * (1 + reduce_ratio)
            sell_ratio = 0.5 * (1 - reduce_ratio)

        return sell_ratio, buy_ratio
```

### 4.3 价格网格分布

```python
# 每10美元一档，动态分配订单数量
GRID_SPACING = 10.0

# 卖单：从ask+gap开始向上
sell_count = int(total_orders * sell_ratio)
for i in range(sell_count):
    price = best_ask + SAFE_GAP + (i * GRID_SPACING)
    if price <= upper_bound:
        sell_orders.append(price)

# 买单：从bid-gap开始向下
buy_count = int(total_orders * buy_ratio)
for i in range(buy_count):
    price = best_bid - SAFE_GAP - (i * GRID_SPACING)
    if price >= lower_bound:
        buy_orders.append(price)
```

---

## 五、风控机制

### 5.1 市场状态判断

```python
# src/risk_manager.py
def check_market_conditions(self, rsi: float, adx: float):
    # 情况1: 强趋势市场 - 触发风控
    if adx > 30:
        return {'allowed': False, 'trigger_cooldown': True}

    # 情况2: 中等趋势市场 - 严格RSI控制
    if adx > 25:
        if rsi < 25 or rsi > 75:
            return {'allowed': False, 'trigger_cooldown': True}
        else:
            return {'allowed': True, 'cautious': True}

    # 情况3: 震荡市场 - 网格最佳环境
    if rsi < 30 or rsi > 70:
        return {'allowed': False, 'trigger_cooldown': True}

    return {'allowed': True}
```

### 5.2 冷却机制

```python
# 触发冷却后的操作
COOLDOWN_MINUTES = 15

if risk_triggered:
    # 1. 取消所有挂单
    await cancel_all_orders()

    # 2. 平仓（如果有仓位）
    if position != 0:
        await close_position(position)

    # 3. 进入15分钟冷却
    risk_manager.trigger_cooldown(reason)
    await asyncio.sleep(COOLDOWN_MINUTES * 60)
```

---

## 六、常见问题排查

### 6.1 SIGNATURE_VERIFICATION (Error 217)

**症状**：CreateSession/PlaceOrder返回错误码217

**排查步骤**：

1. 检查签名是否包含长度前缀
```python
# ✅ 正确
message = length_prefix + payload
signature = sign_func(message)
```

2. 检查签名类型是否正确
```python
# CreateSession: hex编码
user_sign = keypair.sign_message(binascii.hexlify(message))

# PlaceOrder: 直接签名
session_sign = session_keypair.sign_message(message)
```

3. 使用调试脚本验证
```python
# debug_signature.py
payload = action.SerializeToString()
print(f"Payload长度: {len(payload)}")

length_prefix = encode_varint(len(payload))
print(f"长度前缀: {binascii.hexlify(length_prefix)}")

message = length_prefix + payload
print(f"完整消息长度: {len(message)}")

signature = sign_func(message)
print(f"签名长度: {len(signature)}")
```

### 6.2 ADX值异常偏高

**症状**：程序计算的ADX远高于UI显示

**原因**：使用了SMA而非Wilder's Smoothing

**修复**：参考第2.1节，使用标准ADX计算方法

### 6.3 订单无法撤销

**症状**：CancelOrder返回ORDER_NOT_FOUND

**可能原因**：
1. 订单已成交
2. order_id不正确
3. 本地tracker未同步

**排查**：
```python
# 检查order是否存在
order = tracker.find_order_by_price(price, side)
if not order:
    logger.warning(f"订单不存在: {price} {side}")
    return

# 尝试取消
try:
    await cancel_order(order.order_id)
    tracker.remove_order(order.order_id)
except Exception as e:
    if "ORDER_NOT_FOUND" in str(e):
        # 订单可能已成交，从tracker移除
        tracker.remove_order(order.order_id)
```

### 6.4 Session过期

**症状**：PlaceOrder/CancelOrder返回SESSION_EXPIRED

**解决**：实现自动续期机制

```python
# src/api_client.py
SESSION_DURATION = 3600  # 1小时
RENEW_BEFORE = 300       # 提前5分钟

async def ensure_session(self):
    """确保Session有效"""
    if not self.session_id or not self.session_expiry:
        await self.create_session()
        return

    # 检查是否即将过期
    time_remaining = self.session_expiry - time.time()
    if time_remaining < RENEW_BEFORE:
        logger.info("Session即将过期，重新创建")
        await self.create_session()
```

---

## 七、部署指南

### 7.1 VPS快速部署

```bash
# 1. SSH连接VPS
ssh user@vps_ip

# 2. 克隆仓库
git clone https://github.com/YOUR_USERNAME/01exchange-grid-bot.git
cd 01exchange-grid-bot

# 3. 运行一键安装
chmod +x install_vps.sh
./install_vps.sh

# 4. 配置环境变量
nano .env
# 修改SOLANA_PRIVATE_KEY

# 5. 测试运行
source venv/bin/activate
python main.py

# 6. 后台运行（screen）
screen -S gridbot
source venv/bin/activate
python main.py
# Ctrl+A D 分离
```

### 7.2 Systemd服务配置

```bash
# /etc/systemd/system/gridbot.service
[Unit]
Description=01exchange Grid Trading Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/01exchange-grid-bot
Environment="PATH=/home/your_user/01exchange-grid-bot/venv/bin"
ExecStart=/home/your_user/01exchange-grid-bot/venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable gridbot
sudo systemctl start gridbot
sudo systemctl status gridbot
```

### 7.3 监控和日志

```bash
# 查看实时日志
tail -f grid_trader.log

# 搜索错误
grep "ERROR" grid_trader.log

# 查看服务状态
sudo systemctl status gridbot

# 查看服务日志
sudo journalctl -u gridbot -f
```

---

## 八、参数调优建议

### 8.1 基础参数

```ini
# .env
TOTAL_ORDERS=18           # 总订单数
WINDOW_PERCENT=0.12       # 窗口范围±12%
GRID_SPACING=10           # 网格间距10美元
SAFE_GAP=5                # 防瞬成间隙5美元
ORDER_SIZE=0.001          # 单次开仓0.001 BTC
MAX_MULTIPLIER=15         # 最大持仓倍数
```

### 8.2 风控参数

```ini
RSI_MIN=30               # RSI下限
RSI_MAX=70               # RSI上限
ADX_TREND_THRESHOLD=25   # 趋势阈值
ADX_STRONG_TREND=30      # 强趋势阈值
COOLDOWN_MINUTES=15      # 冷却时间
```

### 8.3 调优策略

**震荡市场**（推荐）：
- WINDOW_PERCENT=0.12
- GRID_SPACING=10
- MAX_MULTIPLIER=15

**高波动市场**：
- WINDOW_PERCENT=0.15
- GRID_SPACING=15
- MAX_MULTIPLIER=10

**低波动市场**：
- WINDOW_PERCENT=0.08
- GRID_SPACING=5
- MAX_MULTIPLIER=20

---

## 九、关键代码片段

### 9.1 完整下单流程

```python
async def place_limit_order(self, market_id: int, side: str, price: float, size: float):
    """下限价单"""
    # 1. 确保Session有效
    await self.ensure_session()

    # 2. 生成订单ID
    order_id = int(time.time() * 1000000) % 2147483647

    # 3. 价格精度处理
    price_units = int(price * 1e8)
    size_units = int(abs(size) * 1e8)

    # 4. 构造Action
    action = schema_pb2.Action()
    action.place_order.market_id = market_id
    action.place_order.order_id = order_id
    action.place_order.limit_price.value = price_units

    if side == 'buy':
        action.place_order.size.value = size_units
    else:
        action.place_order.size.value = -size_units

    action.place_order.post_only = True

    # 5. 执行Action
    receipt = await self._execute_action(
        action,
        self.session_keypair,
        self._session_sign
    )

    # 6. 记录到tracker
    order = Order(
        order_id=order_id,
        market_id=market_id,
        side=side,
        price=price,
        size=abs(size),
        timestamp=time.time()
    )
    self.order_tracker.add_order(order)

    return order_id
```

### 9.2 主交易循环

```python
async def run(self):
    """主交易循环"""
    while self.running:
        try:
            # 1. 检查冷却状态
            cooldown_status = self.risk_manager.check_cooldown_status()
            if cooldown_status['in_cooldown']:
                # 撤单+平仓
                await self.cancel_all_orders()
                if self.current_position != 0:
                    await self.close_position()
                await asyncio.sleep(60)
                continue

            # 2. 获取指标
            indicators = await self.indicator_calc.get_indicators('BTC/USDT', '5m')

            # 3. 风控检查
            market_check = self.risk_manager.check_market_conditions(
                indicators['rsi'],
                indicators['adx']
            )

            if not market_check['allowed']:
                # 触发冷却
                self.risk_manager.trigger_cooldown(market_check['reason'])
                await self.cancel_all_orders()
                if self.current_position != 0:
                    await self.close_position()
                continue

            # 4. 获取市场数据
            best_bid, best_ask = await self.api_client.get_best_bid_ask()

            # 5. 计算网格
            grid_orders = self.grid_strategy.calculate_grid(
                best_bid=best_bid,
                best_ask=best_ask,
                position=self.current_position
            )

            # 6. 撤销远单
            await self.cancel_far_orders(grid_orders)

            # 7. 下新订单
            await self.place_grid_orders(grid_orders)

            # 8. 等待下次周期
            await asyncio.sleep(self.cycle_interval)

        except Exception as e:
            logger.error(f"交易循环错误: {e}")
            await asyncio.sleep(60)
```

---

## 十、版本历史

### v2.1 (2026-02-01)
- ✅ 修复ADX计算方法（使用Wilder's Smoothing）
- ✅ 解决ADX值异常偏高导致的错误风控
- ✅ 测试确认ADX现在接近UI显示值

### v2.0 (2026-02-01)
- ✅ 修复签名验证问题（包含长度前缀）
- ✅ 添加Response解析的varint解码
- ✅ 完善本地订单跟踪机制
- ✅ 添加Session自动续期

### v1.0 (2026-02-01)
- ✅ 初始版本
- ✅ 完整网格策略实现
- ✅ RSI/ADX风控机制
- ✅ VPS部署脚本

---

## 十一、参考资料

- **01exchange API文档**: https://zo-mainnet.n1.xyz/schema.proto
- **项目仓库**: https://github.com/wuyutanhongyuxin-cell/01test2
- **成功参考实现**: https://github.com/wuyutanhongyuxin-cell/01_API
- **原始JS脚本作者**: [@ddazmon](https://twitter.com/ddazmon)

---

**最后更新**: 2026-02-01
**维护者**: Claude AI

**⚠️ 免责声明**: 本项目仅供学习研究使用。加密货币交易具有高风险，请务必充分理解风险后再使用。
