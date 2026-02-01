"""
主交易循环和协调器
整合所有模块，实现完整的自动交易逻辑
"""
import asyncio
import logging
import time
from typing import Optional

from .api_client import API01Client
from .indicators import IndicatorCalculator
from .order_tracker import OrderTracker
from .risk_manager import RiskManager
from .grid_strategy import GridStrategy

logger = logging.getLogger(__name__)


class GridTrader:
    """网格交易主控制器"""

    def __init__(self, config):
        """
        初始化交易器

        Args:
            config: 配置对象
        """
        self.config = config

        # 初始化各模块
        self.api_client = API01Client(config.API_URL, config.SOLANA_PRIVATE_KEY)
        self.indicator_calc = IndicatorCalculator('binance')
        self.order_tracker = OrderTracker()
        self.risk_manager = RiskManager(
            rsi_min=config.RSI_MIN,
            rsi_max=config.RSI_MAX,
            adx_trend_threshold=config.ADX_TREND_THRESHOLD,
            adx_strong_trend=config.ADX_STRONG_TREND,
            cooldown_minutes=config.RISK_COOLDOWN_MINUTES
        )
        self.grid_strategy = GridStrategy(
            total_orders=config.TOTAL_ORDERS,
            window_percent=config.WINDOW_PERCENT,
            sell_ratio=config.SELL_RATIO,
            buy_ratio=config.BUY_RATIO,
            base_price_interval=config.BASE_PRICE_INTERVAL,
            safe_gap=config.SAFE_GAP,
            max_drift_buffer=config.MAX_DRIFT_BUFFER,
            min_valid_price=config.MIN_VALID_PRICE,
            max_multiplier=config.MAX_MULTIPLIER
        )

        # 状态管理
        self.is_running = False
        self.cycle_count = 0
        self.last_order_time = 0
        self.current_position = 0.0  # BTC仓位
        self.order_size = 0.001  # 默认开仓大小

    async def initialize(self):
        """初始化连接"""
        logger.info("正在初始化...")

        # 连接API
        await self.api_client.connect()

        # TODO: 从API获取当前仓位（01exchange可能需要从链上查询）
        # 这里暂时使用默认值，实际使用时需要实现

        logger.info("✅ 初始化完成")

    async def cleanup(self):
        """清理资源"""
        logger.info("正在清理资源...")

        await self.api_client.close()
        await self.indicator_calc.close()

        logger.info("清理完成")

    async def start(self):
        """启动交易循环"""
        if self.is_running:
            logger.warning("交易器已在运行")
            return

        self.is_running = True
        self.cycle_count = 0

        logger.info("=" * 60)
        logger.info("🚀 BTC网格交易系统已启动")
        logger.info("=" * 60)

        try:
            while self.is_running:
                start_time = time.time()

                # 执行交易周期
                await self._execute_trading_cycle()

                # 计算下次执行的延迟
                execution_time = time.time() - start_time
                if self.risk_manager.in_cooldown:
                    delay = max(self.config.CHECK_INTERVAL_RISK - execution_time, 1.0)
                else:
                    delay = max(self.config.MONITOR_INTERVAL - execution_time, 1.0)

                await asyncio.sleep(delay)

        except KeyboardInterrupt:
            logger.info("收到停止信号")
        except Exception as e:
            logger.error(f"交易循环异常: {e}", exc_info=True)
        finally:
            self.is_running = False

    def stop(self):
        """停止交易"""
        logger.info("正在停止交易...")
        self.is_running = False

    async def _execute_trading_cycle(self):
        """执行单次交易周期"""
        self.cycle_count += 1
        logger.info(f"\n{'='*60}")
        logger.info(f"第 {self.cycle_count} 次循环 - {time.strftime('%H:%M:%S')}")
        logger.info(f"{'='*60}")

        # 1. 检查风控冷却状态
        cooldown_status = self.risk_manager.check_cooldown_status()
        if cooldown_status['in_cooldown']:
            logger.info(f"🛑 {cooldown_status['message']}")

            # 在冷却期间，定期平仓和撤单
            await self._emergency_close_all()
            return

        # 2. 获取技术指标
        try:
            indicators = await self.indicator_calc.get_indicators(
                symbol='BTC/USDT',
                timeframe='5m'
            )

            if not indicators:
                logger.warning("无法获取指标数据，触发风控")
                self.risk_manager.trigger_cooldown("无法获取指标数据")
                await self._emergency_close_all()
                return

            rsi = indicators['rsi']
            adx = indicators['adx']

            logger.info(f"📊 当前指标 - RSI: {rsi:.2f}, ADX: {adx:.2f}")

        except Exception as e:
            logger.error(f"指标计算失败: {e}")
            self.risk_manager.trigger_cooldown(f"指标计算失败: {e}")
            await self._emergency_close_all()
            return

        # 3. 检查市场条件
        market_check = self.risk_manager.check_market_conditions(rsi, adx)

        if market_check['trigger_cooldown']:
            logger.warning(f"🛑 {market_check['reason']}")
            self.risk_manager.trigger_cooldown(market_check['reason'])
            await self._emergency_close_all()
            return

        if not market_check['allowed']:
            logger.warning(f"⚠️  {market_check['reason']}")
            return

        # 4. 市场条件通过，执行网格策略
        logger.info(f"✅ {market_check['reason']}")

        try:
            await self._execute_grid_strategy()
        except Exception as e:
            logger.error(f"网格策略执行失败: {e}", exc_info=True)
            self.risk_manager.trigger_cooldown(f"策略执行异常: {e}")
            await self._emergency_close_all()

    async def _execute_grid_strategy(self):
        """执行网格策略"""
        # 1. 获取市场数据
        mid_price = await self.api_client.get_mid_price(self.config.MARKET_ID)
        if not mid_price:
            logger.error("无法获取价格，跳过本轮")
            return

        orderbook = await self.api_client.get_orderbook(self.config.MARKET_ID)
        if not orderbook:
            logger.error("无法获取订单簿，跳过本轮")
            return

        # 简化处理：从订单簿提取买卖价
        asks = orderbook.get('asks', [])
        bids = orderbook.get('bids', [])

        if not asks or not bids:
            logger.error("订单簿数据不完整")
            return

        ask_price = float(asks[0][0]) if asks else mid_price + 10
        bid_price = float(bids[0][0]) if bids else mid_price - 10

        logger.info(f"💰 价格 - 买一: ${bid_price:.1f}, 卖一: ${ask_price:.1f}, 中间: ${mid_price:.1f}")

        # 2. 获取现有订单
        existing_sell_prices = self.api_client.get_local_order_prices('sell')
        existing_buy_prices = self.api_client.get_local_order_prices('buy')

        # 3. 计算网格
        grid_result = self.grid_strategy.calculate_grid_prices(
            mid_price=mid_price,
            ask_price=ask_price,
            bid_price=bid_price,
            current_position=self.current_position,
            order_size=self.order_size,
            existing_sell_prices=existing_sell_prices,
            existing_buy_prices=existing_buy_prices
        )

        # 4. 撤销远单
        if grid_result['orders_to_cancel']:
            logger.info(f"开始撤销 {len(grid_result['orders_to_cancel'])} 个远单...")

            for order in grid_result['orders_to_cancel']:
                # 通过价格找到订单ID
                tracked_order = self.order_tracker.get_order_by_price(order['price'])
                if tracked_order:
                    # 尝试撤单，获取状态（'cancelled', 'filled', 'error'）
                    status = await self.api_client.cancel_order(tracked_order.order_id, self.config.MARKET_ID)

                    # 根据状态更新tracker
                    if status in ['cancelled', 'filled']:
                        self.order_tracker.remove_order(tracked_order.order_id, status)

                    await asyncio.sleep(0.5)

            # 撤单后等待
            await asyncio.sleep(1)

        # 5. 重新获取订单状态（撤单后）
        existing_sell_prices = self.api_client.get_local_order_prices('sell')
        existing_buy_prices = self.api_client.get_local_order_prices('buy')

        # 6. 重新计算需要下的单
        grid_result = self.grid_strategy.calculate_grid_prices(
            mid_price=mid_price,
            ask_price=ask_price,
            bid_price=bid_price,
            current_position=self.current_position,
            order_size=self.order_size,
            existing_sell_prices=existing_sell_prices,
            existing_buy_prices=existing_buy_prices
        )

        # 7. 下新单
        await self._place_new_orders(
            grid_result['new_sell_prices'],
            grid_result['new_buy_prices']
        )

        # 8. 打印状态
        self.order_tracker.print_status()

    async def _place_new_orders(self, sell_prices: list, buy_prices: list):
        """下新订单"""
        if not sell_prices and not buy_prices:
            logger.info("无需下新单")
            return

        logger.info(f"开始下单: {len(sell_prices)}卖 + {len(buy_prices)}买")

        # 合并订单
        orders = [
            {'side': 'sell', 'price': p} for p in sell_prices
        ] + [
            {'side': 'buy', 'price': p} for p in buy_prices
        ]

        for order in orders:
            # 检查下单间隔
            if time.time() - self.last_order_time < self.config.MIN_ORDER_INTERVAL:
                await asyncio.sleep(self.config.MIN_ORDER_INTERVAL)

            # 下单
            order_id = await self.api_client.place_order(
                market_id=self.config.MARKET_ID,
                side=order['side'],
                price=order['price'],
                size=self.order_size,
                fill_mode='post_only'  # 使用post_only模式
            )

            if order_id:
                # 添加到本地跟踪
                self.order_tracker.add_order(
                    order_id=order_id,
                    price=order['price'],
                    size=self.order_size,
                    side=order['side'],
                    market_id=self.config.MARKET_ID
                )

                self.last_order_time = time.time()
                await asyncio.sleep(self.config.ORDER_COOLDOWN)

        logger.info("✅ 本轮下单完成")

    async def _emergency_close_all(self):
        """紧急平仓和撤单"""
        logger.warning("执行紧急平仓和撤单...")

        # 取消所有订单
        cancelled_count = await self.api_client.cancel_all_orders(self.config.MARKET_ID)

        # 清空本地跟踪
        self.order_tracker.orders.clear()

        logger.info(f"✅ 已取消 {cancelled_count} 个订单")

        # 市价平仓
        if abs(self.current_position) > 0.0001:  # 有持仓
            try:
                # 获取订单簿获取市价
                orderbook = await self.api_client.get_orderbook(self.config.MARKET_ID)
                if not orderbook:
                    logger.error("无法获取订单簿，无法平仓")
                    return

                asks = orderbook.get('asks', [])
                bids = orderbook.get('bids', [])

                if self.current_position > 0:
                    # 多仓，市价卖出平仓
                    if not bids:
                        logger.error("没有买单，无法平仓")
                        return
                    close_price = float(bids[0][0]) * 0.999  # 稍低于买一价确保成交
                    side = 'sell'
                else:
                    # 空仓，市价买入平仓
                    if not asks:
                        logger.error("没有卖单，无法平仓")
                        return
                    close_price = float(asks[0][0]) * 1.001  # 稍高于卖一价确保成交
                    side = 'buy'

                close_size = abs(self.current_position)
                logger.warning(f"🔴 紧急平仓: {side} {close_size:.5f} BTC @ ${close_price:.1f}")

                # 使用 fill_or_kill 模式强制成交
                order_id = await self.api_client.place_order(
                    market_id=self.config.MARKET_ID,
                    side=side,
                    price=close_price,
                    size=close_size,
                    fill_mode='fill_or_kill',  # 立即全部成交或取消
                    is_reduce_only=True
                )

                if order_id:
                    logger.info(f"✅ 平仓订单已提交: {order_id}")
                    # 重置持仓
                    self.current_position = 0
                else:
                    logger.error("平仓失败")

            except Exception as e:
                logger.error(f"平仓异常: {e}")

    def get_status(self) -> dict:
        """获取状态信息"""
        cooldown_status = self.risk_manager.check_cooldown_status()
        order_stats = self.order_tracker.get_statistics()

        return {
            'is_running': self.is_running,
            'cycle_count': self.cycle_count,
            'current_position': self.current_position,
            'order_size': self.order_size,
            'cooldown': cooldown_status,
            'orders': order_stats
        }
