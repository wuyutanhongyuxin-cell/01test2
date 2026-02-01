"""
网格策略核心逻辑
实现滑动窗口网格策略和动态仓位管理
"""
import logging
import math
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


class GridStrategy:
    """网格策略"""

    def __init__(
        self,
        total_orders: int = 18,
        window_percent: float = 0.12,
        sell_ratio: float = 0.5,
        buy_ratio: float = 0.5,
        base_price_interval: float = 10,
        safe_gap: float = 20,
        max_drift_buffer: float = 2000,
        min_valid_price: float = 10000,
        max_multiplier: float = 15
    ):
        """
        初始化网格策略

        Args:
            total_orders: 总订单数
            window_percent: 窗口宽度百分比
            sell_ratio: 卖单比例
            buy_ratio: 买单比例
            base_price_interval: 基础价格间距
            safe_gap: 安全间隙（防瞬成）
            max_drift_buffer: 最大偏离缓冲
            min_valid_price: 最小有效价格
            max_multiplier: 最大开仓倍数
        """
        self.total_orders = total_orders
        self.window_percent = window_percent
        self.base_sell_ratio = sell_ratio
        self.base_buy_ratio = buy_ratio
        self.base_price_interval = base_price_interval
        self.safe_gap = safe_gap
        self.max_drift_buffer = max_drift_buffer
        self.min_valid_price = min_valid_price
        self.max_multiplier = max_multiplier

    def calculate_position_ratio(
        self,
        current_position: float,
        order_size: float
    ) -> Tuple[float, float, bool]:
        """
        根据当前仓位计算买卖比例

        Args:
            current_position: 当前仓位（正数=多，负数=空）
            order_size: 开仓大小

        Returns:
            (sell_ratio, buy_ratio, is_at_limit)
        """
        if order_size <= 0:
            logger.warning("开仓大小无效，使用默认比例")
            return self.base_sell_ratio, self.base_buy_ratio, False

        # 计算持仓倍数
        position_multiplier = abs(current_position) / order_size

        logger.info(f"当前持仓: {current_position:.4f} BTC | 相对倍数: {position_multiplier:.1f}x")

        # 达到上限，停止对应方向
        if position_multiplier >= self.max_multiplier:
            is_at_limit = True
            if current_position > 0:
                logger.warning(f"⚠️ 多单已达上限({self.max_multiplier}x)，停止开多")
                return 1.0, 0.0, is_at_limit  # 只开卖单
            else:
                logger.warning(f"⚠️ 空单已达上限({self.max_multiplier}x)，停止开空")
                return 0.0, 1.0, is_at_limit  # 只开买单

        # 未达上限，动态调整
        if position_multiplier > 0:
            reduction_ratio = position_multiplier / self.max_multiplier

            if current_position > 0:  # 多单过多，减少买单
                buy_reduction = reduction_ratio * self.base_buy_ratio
                final_buy_ratio = max(0, self.base_buy_ratio - buy_reduction)
                final_sell_ratio = 1 - final_buy_ratio
            else:  # 空单过多，减少卖单
                sell_reduction = reduction_ratio * self.base_sell_ratio
                final_sell_ratio = max(0, self.base_sell_ratio - sell_reduction)
                final_buy_ratio = 1 - final_sell_ratio

            # 确保不会完全为0（除非达到上限）
            final_buy_ratio = max(0.1, min(0.9, final_buy_ratio))
            final_sell_ratio = max(0.1, min(0.9, final_sell_ratio))

            logger.info(f"调整后比例: 卖单 {final_sell_ratio*100:.0f}% / 买单 {final_buy_ratio*100:.0f}%")
            return final_sell_ratio, final_buy_ratio, False

        # 无持仓，使用默认比例
        return self.base_sell_ratio, self.base_buy_ratio, False

    def calculate_grid_prices(
        self,
        mid_price: float,
        ask_price: float,
        bid_price: float,
        current_position: float,
        order_size: float,
        existing_sell_prices: List[float],
        existing_buy_prices: List[float]
    ) -> Dict:
        """
        计算网格价格

        Args:
            mid_price: 中间价
            ask_price: 卖一价
            bid_price: 买一价
            current_position: 当前仓位
            order_size: 开仓大小
            existing_sell_prices: 现有卖单价格
            existing_buy_prices: 现有买单价格

        Returns:
            包含新订单和需要撤销订单的字典
        """
        # 计算窗口范围
        window_size = mid_price * self.window_percent
        half_window = window_size / 2

        logger.info(f"中间价 ${mid_price:.1f} | 窗口 ±${half_window:.0f}")

        # 计算动态买卖比例
        sell_ratio, buy_ratio, is_at_limit = self.calculate_position_ratio(
            current_position, order_size
        )

        # 计算各方向订单数
        sell_count = round(self.total_orders * sell_ratio)
        buy_count = self.total_orders - sell_count

        # 生成理想价格
        ideal_sell_prices = self._generate_sell_prices(
            ask_price, mid_price, half_window, sell_count
        )
        ideal_buy_prices = self._generate_buy_prices(
            bid_price, mid_price, half_window, buy_count
        )

        # 计算新订单
        new_sell_prices = [p for p in ideal_sell_prices if p not in existing_sell_prices]
        new_buy_prices = [p for p in ideal_buy_prices if p not in existing_buy_prices]

        # 计算需要撤销的订单
        ideal_prices_set = set(ideal_sell_prices + ideal_buy_prices)
        orders_to_cancel = self._find_orders_to_cancel(
            existing_sell_prices,
            existing_buy_prices,
            ideal_prices_set,
            mid_price,
            sell_count,
            buy_count
        )

        # 统计
        current_total = len(existing_sell_prices) + len(existing_buy_prices)
        logger.info(f"当前订单: {len(existing_sell_prices)}卖 + {len(existing_buy_prices)}买 = {current_total}")
        logger.info(f"目标订单: {len(ideal_sell_prices)}卖 + {len(ideal_buy_prices)}买")
        logger.info(f"需下单: {len(new_sell_prices)}卖 + {len(new_buy_prices)}买")

        if orders_to_cancel:
            logger.info(f"需撤销: {len(orders_to_cancel)}单")
        else:
            logger.info("无需撤销订单")

        return {
            'new_sell_prices': new_sell_prices,
            'new_buy_prices': new_buy_prices,
            'orders_to_cancel': orders_to_cancel,
            'sell_count': sell_count,
            'buy_count': buy_count
        }

    def _generate_sell_prices(
        self,
        ask_price: float,
        mid_price: float,
        half_window: float,
        count: int
    ) -> List[float]:
        """生成卖单价格"""
        if count == 0:
            return []

        interval = self.base_price_interval
        start_price = math.ceil((ask_price + self.safe_gap) / interval) * interval

        prices = []
        for i in range(count):
            price = start_price + i * interval

            # 超出窗口范围，停止
            if price > mid_price + half_window + self.max_drift_buffer:
                break

            prices.append(price)

        return prices

    def _generate_buy_prices(
        self,
        bid_price: float,
        mid_price: float,
        half_window: float,
        count: int
    ) -> List[float]:
        """生成买单价格"""
        if count == 0:
            return []

        interval = self.base_price_interval
        start_price = math.floor((bid_price - self.safe_gap) / interval) * interval

        prices = []
        for i in range(count):
            price = start_price - i * interval

            # 超出窗口范围，停止
            if price < mid_price - half_window - self.max_drift_buffer:
                break

            # 防止崩盘价
            if price < self.min_valid_price:
                break

            prices.append(price)

        return prices

    def _find_orders_to_cancel(
        self,
        existing_sell_prices: List[float],
        existing_buy_prices: List[float],
        ideal_prices_set: set,
        mid_price: float,
        target_sell_count: int,
        target_buy_count: int
    ) -> List[Dict]:
        """找出需要撤销的订单"""
        current_total = len(existing_sell_prices) + len(existing_buy_prices)
        orders_to_cancel = []

        # 如果总数超标，或某方向超标
        if (current_total > self.total_orders or
            len(existing_sell_prices) > target_sell_count or
            len(existing_buy_prices) > target_buy_count):

            # 找出偏离理想价格的订单
            far_sell_orders = [
                {'type': 'sell', 'price': p}
                for p in existing_sell_prices
                if p not in ideal_prices_set
            ]
            far_buy_orders = [
                {'type': 'buy', 'price': p}
                for p in existing_buy_prices
                if p not in ideal_prices_set
            ]

            # 合并并按距离中间价远近排序
            all_far = far_sell_orders + far_buy_orders
            all_far.sort(key=lambda x: abs(x['price'] - mid_price), reverse=True)

            # 计算需要撤销的数量
            excess = current_total - self.total_orders
            cancel_count = max(excess, len(all_far))

            # 最多一次撤10个，防止过激
            orders_to_cancel = all_far[:min(cancel_count, 10)]

        return orders_to_cancel

    def should_skip_cancel(
        self,
        order_price: float,
        current_price: float
    ) -> bool:
        """
        判断是否应该跳过撤单（如果订单价格接近当前价格）

        Args:
            order_price: 订单价格
            current_price: 当前价格

        Returns:
            True if should skip
        """
        price_diff = abs(order_price - current_price)
        threshold = self.base_price_interval * (self.max_multiplier / 4)

        return price_diff <= threshold
