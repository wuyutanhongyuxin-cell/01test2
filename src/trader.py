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
        # 从配置读取初始持仓（正数=多仓，负数=空仓）
        self.current_position = config.INITIAL_POSITION
        self.order_size = config.ORDER_SIZE  # 从配置读取开仓大小

    async def initialize(self):
        """初始化连接"""
        logger.info("正在初始化...")

        # 连接API
        await self.api_client.connect()

        # 显示初始持仓
        if abs(self.current_position) > 0.0001:
            direction = "多仓" if self.current_position > 0 else "空仓"
            logger.info(f"📊 初始持仓: {direction} {abs(self.current_position):.5f} BTC (来自INITIAL_POSITION配置)")
        else:
            logger.info("📊 初始持仓: 无")

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
                timeframe=self.config.INDICATOR_TIMEFRAME
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
                        # 如果订单已成交，更新持仓
                        if status == 'filled':
                            if tracked_order.side == 'buy':
                                self.current_position += tracked_order.size
                            else:
                                self.current_position -= tracked_order.size
                            logger.info(f"📈 订单成交，持仓更新: {self.current_position:.5f} BTC")

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

        # 市价平仓 - 即使持仓跟踪可能不准，也尝试平仓
        # 如果实际没有持仓，reduce_only订单会被交易所拒绝，这是正常的
        if abs(self.current_position) > 0.0001:
            await self._try_close_position()
        else:
            logger.info("📊 当前无持仓记录，跳过平仓")

    async def _try_close_position(self):
        """尝试平仓当前持仓"""
        try:
            # 获取订单簿获取市价
            orderbook = await self.api_client.get_orderbook(self.config.MARKET_ID)
            if not orderbook:
                logger.error("无法获取订单簿，无法平仓")
                return False

            asks = orderbook.get('asks', [])
            bids = orderbook.get('bids', [])

            if self.current_position > 0:
                # 多仓，市价卖出平仓
                if not bids:
                    logger.error("没有买单，无法平仓")
                    return False
                # 使用比买一价低0.5%的价格确保成交
                close_price = float(bids[0][0]) * 0.995
                side = 'sell'
            else:
                # 空仓，市价买入平仓
                if not asks:
                    logger.error("没有卖单，无法平仓")
                    return False
                # 使用比卖一价高0.5%的价格确保成交
                close_price = float(asks[0][0]) * 1.005
                side = 'buy'

            close_size = abs(self.current_position)
            logger.warning(f"🔴 紧急平仓: {side} {close_size:.5f} BTC @ ${close_price:.1f}")

            # 使用 immediate 模式（立即成交或取消）+ reduce_only
            # 01exchange在平仓时要求使用IMMEDIATE_OR_CANCEL模式
            order_id = await self.api_client.place_order(
                market_id=self.config.MARKET_ID,
                side=side,
                price=close_price,
                size=close_size,
                fill_mode='immediate',  # 使用立即成交模式
                is_reduce_only=True  # 只减仓，确保不会开新仓
            )

            if order_id:
                logger.info(f"✅ 平仓订单已提交: order_id={order_id}")
                # 重置持仓（假设订单会成交）
                self.current_position = 0
                return True
            else:
                logger.warning("⚠️ 平仓订单提交失败（可能实际无持仓）")
                return False

        except Exception as e:
            logger.error(f"平仓异常: {e}")
            return False

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
