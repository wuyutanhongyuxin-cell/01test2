"""
本地订单跟踪管理器
由于01exchange没有查询订单的API，需要在本地维护订单状态
"""
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """订单数据结构"""
    order_id: int
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    market_id: int
    timestamp: float
    status: str = 'open'  # 'open', 'filled', 'cancelled'


class OrderTracker:
    """订单跟踪器"""

    def __init__(self, max_history: int = 1000):
        """
        初始化订单跟踪器

        Args:
            max_history: 最大历史记录数
        """
        self.orders: Dict[int, Order] = {}  # order_id -> Order
        self.history: List[Order] = []  # 历史订单
        self.max_history = max_history

    def add_order(
        self,
        order_id: int,
        price: float,
        size: float,
        side: str,
        market_id: int = 0
    ):
        """添加订单到跟踪"""
        order = Order(
            order_id=order_id,
            price=price,
            size=size,
            side=side,
            market_id=market_id,
            timestamp=time.time(),
            status='open'
        )
        self.orders[order_id] = order
        logger.debug(f"跟踪新订单: {side} {size} @ ${price} (ID: {order_id})")

    def remove_order(self, order_id: int, reason: str = 'cancelled'):
        """
        移除订单（成交或取消）

        Args:
            order_id: 订单ID
            reason: 'filled' 或 'cancelled'
        """
        if order_id in self.orders:
            order = self.orders[order_id]
            order.status = reason

            # 移到历史记录
            self.history.append(order)
            if len(self.history) > self.max_history:
                self.history.pop(0)

            # 从活跃订单中移除
            del self.orders[order_id]

            logger.debug(f"订单 {order_id} 已{reason}")

    def get_open_orders(self, side: Optional[str] = None) -> List[Order]:
        """
        获取未成交订单

        Args:
            side: 'buy', 'sell' 或 None（全部）

        Returns:
            订单列表
        """
        orders = list(self.orders.values())
        if side:
            orders = [o for o in orders if o.side == side]
        return sorted(orders, key=lambda x: x.price)

    def get_order_prices(self, side: str) -> List[float]:
        """获取指定方向的所有订单价格"""
        orders = self.get_open_orders(side)
        return [o.price for o in orders]

    def get_order_by_price(self, price: float, tolerance: float = 1.0) -> Optional[Order]:
        """
        根据价格查找订单（允许误差）

        Args:
            price: 目标价格
            tolerance: 允许的价格误差

        Returns:
            匹配的订单
        """
        for order in self.orders.values():
            if abs(order.price - price) < tolerance:
                return order
        return None

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        buy_orders = self.get_open_orders('buy')
        sell_orders = self.get_open_orders('sell')

        filled_orders = [o for o in self.history if o.status == 'filled']
        cancelled_orders = [o for o in self.history if o.status == 'cancelled']

        return {
            'total_open': len(self.orders),
            'buy_orders': len(buy_orders),
            'sell_orders': len(sell_orders),
            'total_filled': len(filled_orders),
            'total_cancelled': len(cancelled_orders),
            'history_size': len(self.history)
        }

    def clear_old_history(self, max_age_hours: int = 24):
        """清理旧的历史记录"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        self.history = [o for o in self.history if o.timestamp > cutoff_time]
        logger.info(f"清理旧历史记录，保留 {len(self.history)} 条")

    def print_status(self):
        """打印当前状态"""
        stats = self.get_statistics()
        logger.info("=" * 50)
        logger.info(f"未成交订单: {stats['total_open']} (买: {stats['buy_orders']}, 卖: {stats['sell_orders']})")
        logger.info(f"历史记录: 成交 {stats['total_filled']}, 取消 {stats['total_cancelled']}")
        logger.info("=" * 50)

        # 打印订单详情
        buy_orders = self.get_open_orders('buy')
        sell_orders = self.get_open_orders('sell')

        if buy_orders:
            logger.info("买单:")
            for order in buy_orders[-5:]:  # 只显示最近5个
                logger.info(f"  ${order.price:.1f} x {order.size:.4f}")

        if sell_orders:
            logger.info("卖单:")
            for order in sell_orders[:5]:  # 只显示最近5个
                logger.info(f"  ${order.price:.1f} x {order.size:.4f}")
