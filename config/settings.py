"""
配置管理模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """统一配置管理"""

    # ========== API配置 ==========
    API_URL = os.getenv('API_URL', 'https://zo-mainnet.n1.xyz')
    SOLANA_PRIVATE_KEY = os.getenv('SOLANA_PRIVATE_KEY', '')

    # ========== 交易配置 ==========
    SYMBOL = os.getenv('SYMBOL', 'BTCUSD')
    MARKET_ID = int(os.getenv('MARKET_ID', '0'))

    # ========== 网格策略参数 ==========
    ORDER_SIZE = float(os.getenv('ORDER_SIZE', '0.001'))
    TOTAL_ORDERS = int(os.getenv('TOTAL_ORDERS', '18'))
    WINDOW_PERCENT = float(os.getenv('WINDOW_PERCENT', '0.12'))
    SELL_RATIO = float(os.getenv('SELL_RATIO', '0.5'))
    BUY_RATIO = float(os.getenv('BUY_RATIO', '0.5'))
    BASE_PRICE_INTERVAL = float(os.getenv('BASE_PRICE_INTERVAL', '10'))
    SAFE_GAP = float(os.getenv('SAFE_GAP', '20'))
    MAX_DRIFT_BUFFER = float(os.getenv('MAX_DRIFT_BUFFER', '2000'))
    MIN_VALID_PRICE = float(os.getenv('MIN_VALID_PRICE', '10000'))
    MAX_MULTIPLIER = float(os.getenv('MAX_MULTIPLIER', '15'))

    # ========== 指标参数 ==========
    INDICATOR_TIMEFRAME = os.getenv('INDICATOR_TIMEFRAME', '5m')

    # ========== 风控参数 ==========
    RSI_MIN = float(os.getenv('RSI_MIN', '30'))
    RSI_MAX = float(os.getenv('RSI_MAX', '70'))
    ADX_TREND_THRESHOLD = float(os.getenv('ADX_TREND_THRESHOLD', '25'))
    ADX_STRONG_TREND = float(os.getenv('ADX_STRONG_TREND', '30'))
    RISK_COOLDOWN_MINUTES = int(os.getenv('RISK_COOLDOWN_MINUTES', '15'))

    # ========== 时间参数（秒） ==========
    MIN_ORDER_INTERVAL = int(os.getenv('MIN_ORDER_INTERVAL', '8000')) / 1000
    ORDER_COOLDOWN = int(os.getenv('ORDER_COOLDOWN', '4000')) / 1000
    MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL', '10000')) / 1000
    CHECK_INTERVAL_RISK = int(os.getenv('CHECK_INTERVAL_RISK', '10000')) / 1000

    # ========== 日志配置 ==========
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    @classmethod
    def validate(cls):
        """验证配置"""
        if not cls.SOLANA_PRIVATE_KEY:
            raise ValueError("SOLANA_PRIVATE_KEY is required")

        if cls.SELL_RATIO + cls.BUY_RATIO != 1.0:
            raise ValueError("SELL_RATIO + BUY_RATIO must equal 1.0")

        return True


# 全局配置实例
config = Config()
