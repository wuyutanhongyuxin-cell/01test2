"""
01exchange Grid Trading Bot - 主启动文件
"""
import asyncio
import logging
import sys
from config import config
from src.trader import GridTrader


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('grid_trader.log', encoding='utf-8')
        ]
    )


async def main():
    """主函数"""
    # 配置日志
    setup_logging()
    logger = logging.getLogger(__name__)

    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        logger.error("请检查 .env 文件配置")
        return

    # 打印启动信息
    logger.info("=" * 60)
    logger.info("01exchange Grid Trading Bot")
    logger.info("=" * 60)
    logger.info(f"API地址: {config.API_URL}")
    logger.info(f"交易对: {config.SYMBOL} (Market ID: {config.MARKET_ID})")
    logger.info(f"网格配置: {config.TOTAL_ORDERS}单, 窗口{config.WINDOW_PERCENT*100}%")
    logger.info(f"买卖比例: {config.SELL_RATIO*100:.0f}% / {config.BUY_RATIO*100:.0f}%")
    logger.info(f"风控: RSI {config.RSI_MIN}-{config.RSI_MAX}, ADX阈值 {config.ADX_TREND_THRESHOLD}/{config.ADX_STRONG_TREND}")
    logger.info("=" * 60)

    # 创建交易器
    trader = GridTrader(config)

    try:
        # 初始化
        await trader.initialize()

        # 启动交易
        await trader.start()

    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在退出...")
    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
    finally:
        # 清理资源
        await trader.cleanup()
        logger.info("程序已退出")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已终止")
