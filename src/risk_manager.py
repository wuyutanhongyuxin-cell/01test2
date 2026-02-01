"""
风控管理器
实现基于RSI/ADX的风控冷却机制
"""
import logging
import time
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RiskManager:
    """风控管理器"""

    def __init__(
        self,
        rsi_min: float = 30,
        rsi_max: float = 70,
        adx_trend_threshold: float = 25,
        adx_strong_trend: float = 30,
        cooldown_minutes: int = 15
    ):
        """
        初始化风控管理器

        Args:
            rsi_min: RSI下限
            rsi_max: RSI上限
            adx_trend_threshold: ADX趋势阈值
            adx_strong_trend: ADX强趋势阈值
            cooldown_minutes: 冷却时间（分钟）
        """
        self.rsi_min = rsi_min
        self.rsi_max = rsi_max
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_strong_trend = adx_strong_trend
        self.cooldown_minutes = cooldown_minutes

        # 冷却状态
        self.in_cooldown = False
        self.cooldown_end_time: Optional[float] = None
        self.cooldown_reason: str = ''

    def check_market_conditions(
        self,
        rsi: Optional[float],
        adx: Optional[float]
    ) -> Dict[str, any]:
        """
        检查市场条件

        Args:
            rsi: RSI值
            adx: ADX值

        Returns:
            检查结果字典
        """
        # 如果无法获取指标，触发风控
        if rsi is None or adx is None:
            return {
                'allowed': False,
                'trigger_cooldown': True,
                'reason': '无法获取完整指标数据',
                'market_type': 'unknown'
            }

        # 情况1: 强趋势市场 - 触发风控
        if adx > self.adx_strong_trend:
            return {
                'allowed': False,
                'trigger_cooldown': True,
                'reason': f'强趋势市场 (ADX: {adx:.2f} > {self.adx_strong_trend})',
                'market_type': 'strong_trend'
            }

        # 情况2: 中等趋势市场
        if adx > self.adx_trend_threshold:
            # 在趋势市场中，需要更严格的RSI控制
            trend_rsi_tolerance = 5
            if rsi < (self.rsi_min - trend_rsi_tolerance) or rsi > (self.rsi_max + trend_rsi_tolerance):
                return {
                    'allowed': False,
                    'trigger_cooldown': True,
                    'reason': f'趋势市场中RSI({rsi:.2f})过于极端',
                    'market_type': 'moderate_trend'
                }

            # 趋势市场但RSI可控
            return {
                'allowed': True,
                'trigger_cooldown': False,
                'reason': f'趋势市场但RSI在可控范围内 (ADX: {adx:.2f}, RSI: {rsi:.2f})',
                'market_type': 'moderate_trend',
                'cautious': True
            }

        # 情况3: 震荡市场 - 最适合网格
        if rsi < self.rsi_min or rsi > self.rsi_max:
            return {
                'allowed': False,
                'trigger_cooldown': True,
                'reason': f'RSI({rsi:.2f})不在{self.rsi_min}-{self.rsi_max}震荡区间',
                'market_type': 'ranging'
            }

        # 理想状态：震荡市场且RSI在区间内
        return {
            'allowed': True,
            'trigger_cooldown': False,
            'reason': f'震荡市场且RSI在区间内 (ADX: {adx:.2f}, RSI: {rsi:.2f})',
            'market_type': 'ranging'
        }

    def trigger_cooldown(self, reason: str):
        """
        触发风控冷却

        Args:
            reason: 触发原因
        """
        self.in_cooldown = True
        self.cooldown_reason = reason
        self.cooldown_end_time = time.time() + (self.cooldown_minutes * 60)

        end_time_str = datetime.fromtimestamp(self.cooldown_end_time).strftime('%H:%M:%S')

        logger.warning("=" * 60)
        logger.warning(f"⚠️  触发风控冷却: {reason}")
        logger.warning(f"⏰ 冷却时间: {self.cooldown_minutes}分钟，预计恢复: {end_time_str}")
        logger.warning("=" * 60)

    def check_cooldown_status(self) -> Dict[str, any]:
        """
        检查冷却状态

        Returns:
            冷却状态信息
        """
        if not self.in_cooldown:
            return {
                'in_cooldown': False,
                'message': '风控冷却未激活'
            }

        # 检查是否已过冷却期
        current_time = time.time()
        if current_time >= self.cooldown_end_time:
            self.in_cooldown = False
            self.cooldown_reason = ''
            logger.info("✅ 风控冷却已结束，恢复交易")
            return {
                'in_cooldown': False,
                'message': '风控冷却已结束'
            }

        # 仍在冷却中
        remaining_seconds = self.cooldown_end_time - current_time
        remaining_minutes = int(remaining_seconds // 60)
        remaining_secs = int(remaining_seconds % 60)
        end_time_str = datetime.fromtimestamp(self.cooldown_end_time).strftime('%H:%M:%S')

        return {
            'in_cooldown': True,
            'reason': self.cooldown_reason,
            'remaining_minutes': remaining_minutes,
            'remaining_seconds': remaining_secs,
            'end_time': end_time_str,
            'message': f'风控冷却中 - {self.cooldown_reason}，剩余: {remaining_minutes}分{remaining_secs}秒，预计恢复: {end_time_str}'
        }

    def reset_cooldown(self):
        """手动重置风控冷却"""
        self.in_cooldown = False
        self.cooldown_end_time = None
        self.cooldown_reason = ''
        logger.info("✅ 风控冷却已手动重置")

    def get_status_summary(self, rsi: Optional[float], adx: Optional[float]) -> str:
        """
        获取状态摘要

        Args:
            rsi: 当前RSI
            adx: 当前ADX

        Returns:
            状态摘要字符串
        """
        cooldown_status = self.check_cooldown_status()

        if cooldown_status['in_cooldown']:
            return f"🛑 {cooldown_status['message']}"

        if rsi is None or adx is None:
            return "⚠️  无法获取指标数据"

        check_result = self.check_market_conditions(rsi, adx)

        if check_result['allowed']:
            if check_result.get('cautious'):
                return f"⚠️  谨慎允许 - {check_result['reason']}"
            else:
                return f"✅ 允许交易 - {check_result['reason']}"
        else:
            return f"🛑 风控触发 - {check_result['reason']}"


# 测试代码
if __name__ == '__main__':
    risk_mgr = RiskManager()

    # 测试场景1: 强趋势市场
    print("\n测试1: 强趋势市场")
    result = risk_mgr.check_market_conditions(rsi=55, adx=35)
    print(f"结果: {result}")

    # 测试场景2: 震荡市场，RSI正常
    print("\n测试2: 震荡市场，RSI正常")
    result = risk_mgr.check_market_conditions(rsi=50, adx=20)
    print(f"结果: {result}")

    # 测试场景3: 震荡市场，RSI超买
    print("\n测试3: 震荡市场，RSI超买")
    result = risk_mgr.check_market_conditions(rsi=75, adx=20)
    print(f"结果: {result}")

    # 测试冷却
    print("\n测试4: 触发冷却")
    risk_mgr.trigger_cooldown("测试冷却")
    status = risk_mgr.check_cooldown_status()
    print(f"冷却状态: {status['message']}")
