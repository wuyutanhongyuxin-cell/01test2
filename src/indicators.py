"""
技术指标计算模块
实现RSI、ADX等指标的计算
"""
import logging
from typing import Optional, Dict, List
import numpy as np
import pandas as pd
import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """技术指标计算器"""

    def __init__(self, exchange_id: str = 'binance'):
        """
        初始化指标计算器

        Args:
            exchange_id: 用于获取K线数据的交易所（默认Binance，因为01exchange可能没有公开K线API）
        """
        self.exchange = getattr(ccxt, exchange_id)()
        self._cache: Dict = {}
        self._cache_time: float = 0

    async def close(self):
        """关闭交易所连接"""
        await self.exchange.close()

    async def fetch_ohlcv(
        self,
        symbol: str = 'BTC/USDT',
        timeframe: str = '5m',
        limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        获取K线数据

        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            limit: 数据条数

        Returns:
            包含OHLCV的DataFrame
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            return df

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return None

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> Optional[float]:
        """
        计算RSI指标 - 使用标准Wilder's Smoothing方法

        Args:
            prices: 价格序列
            period: 周期（默认14）

        Returns:
            当前RSI值
        """
        if len(prices) < period + 1:
            return None

        # 计算价格变化
        delta = prices.diff()

        # 分离涨跌
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # 使用Wilder's Smoothing（与ADX相同）
        # alpha = 1/period，对应 span = 2*period - 1
        wilder_span = 2 * period - 1

        avg_gain = gain.ewm(span=wilder_span, adjust=False).mean()
        avg_loss = loss.ewm(span=wilder_span, adjust=False).mean()

        # 计算RS和RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1])

    @staticmethod
    def calculate_adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> Optional[float]:
        """
        计算ADX指标（趋势强度）- 使用标准Wilder's Smoothing方法

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 周期（默认14）

        Returns:
            当前ADX值
        """
        if len(high) < period * 2:  # ADX需要更多数据
            return None

        # 计算真实波幅TR
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # 计算方向移动 +DM 和 -DM
        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=high.index)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=high.index)

        # 使用Wilder's Smoothing（EMA with alpha=1/period）进行平滑
        # 相当于 ewm(span=period, adjust=False) 但Wilder使用的是alpha=1/period
        # ewm的span和alpha关系：alpha = 2/(span+1)，所以 span = (2/alpha) - 1
        # 对于Wilder的alpha=1/14，span = (2*14) - 1 = 27
        wilder_span = 2 * period - 1

        atr = tr.ewm(span=wilder_span, adjust=False).mean()
        plus_dm_smooth = plus_dm.ewm(span=wilder_span, adjust=False).mean()
        minus_dm_smooth = minus_dm.ewm(span=wilder_span, adjust=False).mean()

        # 计算DI
        plus_di = 100 * plus_dm_smooth / atr
        minus_di = 100 * minus_dm_smooth / atr

        # 计算DX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)

        # 计算ADX（对DX再次使用Wilder's Smoothing）
        adx = dx.ewm(span=wilder_span, adjust=False).mean()

        return float(adx.iloc[-1])

    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
        """
        计算EMA（指数移动平均）

        Args:
            prices: 价格序列
            period: 周期

        Returns:
            EMA序列
        """
        return prices.ewm(span=period, adjust=False).mean()

    async def get_indicators(
        self,
        symbol: str = 'BTC/USDT',
        timeframe: str = '5m',
        rsi_period: int = 14,
        adx_period: int = 14
    ) -> Optional[Dict]:
        """
        一次性获取所有需要的指标

        Args:
            symbol: 交易对
            timeframe: 时间周期
            rsi_period: RSI周期
            adx_period: ADX周期

        Returns:
            包含各指标的字典
        """
        # 获取K线数据
        df = await self.fetch_ohlcv(symbol, timeframe, limit=100)
        if df is None or len(df) < max(rsi_period, adx_period) + 1:
            logger.warning("K线数据不足，无法计算指标")
            return None

        try:
            # 计算RSI
            rsi = self.calculate_rsi(df['close'], rsi_period)

            # 计算ADX
            adx = self.calculate_adx(df['high'], df['low'], df['close'], adx_period)

            # 计算EMA
            ema9 = self.calculate_ema(df['close'], 9).iloc[-1]
            ema21 = self.calculate_ema(df['close'], 21).iloc[-1]

            result = {
                'rsi': rsi,
                'adx': adx,
                'ema9': float(ema9),
                'ema21': float(ema21),
                'current_price': float(df['close'].iloc[-1]),
                'timestamp': df['timestamp'].iloc[-1]
            }

            logger.debug(f"指标计算结果: RSI={rsi:.2f}, ADX={adx:.2f}")
            return result

        except Exception as e:
            logger.error(f"指标计算失败: {e}")
            return None


# 简化的测试函数
async def test_indicators():
    """测试指标计算"""
    calc = IndicatorCalculator('binance')

    try:
        indicators = await calc.get_indicators('BTC/USDT', '5m')
        if indicators:
            print(f"RSI: {indicators['rsi']:.2f}")
            print(f"ADX: {indicators['adx']:.2f}")
            print(f"EMA9: {indicators['ema9']:.2f}")
            print(f"EMA21: {indicators['ema21']:.2f}")
            print(f"Price: {indicators['current_price']:.2f}")
    finally:
        await calc.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_indicators())
