"""
01exchange API客户端封装
基于Protobuf协议实现下单、撤单、查询等功能
"""
import asyncio
import time
import logging
import binascii
from typing import Dict, Optional, List
import aiohttp
from solders.keypair import Keypair
from solders.pubkey import Pubkey

logger = logging.getLogger(__name__)

# 由于protobuf schema需要从服务器下载并编译，这里使用动态导入
# 实际使用时需要先执行: curl -o schema.proto {API_URL}/schema.proto && protoc --python_out=. schema.proto
try:
    import schema_pb2
except ImportError:
    logger.warning("schema_pb2 not found, please compile schema.proto first")
    schema_pb2 = None


class API01Client:
    """01exchange API客户端"""

    def __init__(self, api_url: str, private_key: str):
        """
        初始化API客户端

        Args:
            api_url: API地址（主网或测试网）
            private_key: Solana钱包私钥（Base58格式）
        """
        self.api_url = api_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None

        # 初始化密钥对
        try:
            self.keypair = Keypair.from_base58_string(private_key)
            self.session_keypair = Keypair()  # 生成临时会话密钥对
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")

        # 会话管理
        self.trading_session_id: Optional[int] = None
        self.session_expiry: Optional[int] = None

        # 本地订单跟踪
        self._local_orders: Dict[int, Dict] = {}

        # 市场信息缓存
        self._market_info: Optional[Dict] = None
        self._price_decimals: int = 1
        self._size_decimals: int = 4

    async def connect(self):
        """建立连接并初始化"""
        self.session = aiohttp.ClientSession()

        # 获取市场信息
        await self._fetch_market_info()

        # 创建交易会话
        await self._create_trading_session()

        logger.info(f"✅ 已连接到 {self.api_url}")

    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()
        logger.info("连接已关闭")

    # ==================== 市场数据 ====================

    async def _fetch_market_info(self):
        """获取市场信息"""
        async with self.session.get(f"{self.api_url}/info") as resp:
            data = await resp.json()
            self._market_info = data

            # 解析精度信息
            if 'markets' in data and len(data['markets']) > 0:
                market = data['markets'][0]
                self._price_decimals = market.get('priceDecimals', 1)
                self._size_decimals = market.get('sizeDecimals', 4)

            logger.info(f"市场精度: price={self._price_decimals}, size={self._size_decimals}")

    async def get_market_stats(self, market_id: int = 0) -> Optional[Dict]:
        """
        获取市场统计数据

        Returns:
            包含mark_price, index_price等的字典
        """
        try:
            async with self.session.get(f"{self.api_url}/market/{market_id}/stats") as resp:
                data = await resp.json()
                return data
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return None

    async def get_mid_price(self, market_id: int = 0) -> Optional[float]:
        """获取中间价"""
        stats = await self.get_market_stats(market_id)
        if stats and 'perpStats' in stats:
            mark_price = stats['perpStats'].get('mark_price')
            if mark_price:
                return float(mark_price)
        return None

    async def get_orderbook(self, market_id: int = 0) -> Optional[Dict]:
        """获取订单簿"""
        try:
            async with self.session.get(f"{self.api_url}/market/{market_id}/orderbook") as resp:
                if resp.status != 200:
                    logger.error(f"获取订单簿失败: HTTP {resp.status}")
                    return None
                data = await resp.json()
                return data
        except Exception as e:
            logger.error(f"获取订单簿失败: {e}")
            return None

    async def get_server_time(self) -> int:
        """获取服务器时间戳"""
        try:
            async with self.session.get(f"{self.api_url}/timestamp") as resp:
                text = await resp.text()
                # API现在直接返回整数，不是JSON
                return int(text.strip())
        except Exception as e:
            logger.warning(f"获取服务器时间失败，使用本地时间: {e}")
            return int(time.time())

    # ==================== 会话管理 ====================

    async def _create_trading_session(self):
        """创建交易会话"""
        if not schema_pb2:
            raise RuntimeError("schema_pb2 not available")

        # 每次创建新的session_keypair，避免DUPLICATE错误
        from solders.keypair import Keypair
        self.session_keypair = Keypair()

        server_time = await self.get_server_time()
        expiry_timestamp = server_time + 3600  # 1小时有效期

        # 构建CreateSession消息
        action = schema_pb2.Action()
        action.current_timestamp = server_time
        action.nonce = 0
        action.create_session.user_pubkey = bytes(self.keypair.pubkey())
        action.create_session.session_pubkey = bytes(self.session_keypair.pubkey())
        action.create_session.expiry_timestamp = expiry_timestamp

        # 执行并获取session_id
        receipt = await self._execute_action(action, self.keypair, self._user_sign)

        if receipt.HasField("err"):
            error_name = schema_pb2.Error.Name(receipt.err)
            raise RuntimeError(f"创建会话失败: {error_name}")

        # 从返回中提取session_id
        if receipt.HasField("create_session_result"):
            self.trading_session_id = receipt.create_session_result.session_id
            logger.info(f"✅ 交易会话已创建: session_id={self.trading_session_id}")
        else:
            raise RuntimeError("CreateSession返回中没有session_id")

        # 使用本地时间记录Session创建时间，避免服务器时间和本地时间不一致
        self.session_created_at = time.time()
        self.session_expiry = expiry_timestamp  # 保留用于其他用途

    async def _check_session_validity(self):
        """检查会话是否有效，过期则重新创建"""
        # 使用本地时间计算Session存活时间
        if hasattr(self, 'session_created_at'):
            elapsed = time.time() - self.session_created_at
            # Session 1小时过期，提前5分钟续期 = 55分钟
            if elapsed >= 55 * 60:
                logger.warning(f"⚠️ 会话已存活{int(elapsed/60)}分钟，重新创建...")
                self.trading_session_id = None
                await self._create_trading_session()
        elif not self.trading_session_id:
            # 没有Session，创建新的
            await self._create_trading_session()

    # ==================== 签名方法 ====================

    def _user_sign(self, message: bytes) -> bytes:
        """用户签名（用于CreateSession）"""
        hex_msg = binascii.hexlify(message)
        return bytes(self.keypair.sign_message(hex_msg))

    def _session_sign(self, message: bytes) -> bytes:
        """会话签名（用于PlaceOrder/CancelOrder）"""
        return bytes(self.session_keypair.sign_message(message))

    def _encode_varint(self, value: int) -> bytes:
        """Varint编码"""
        bits = value & 0x7f
        value >>= 7
        result = b''
        while value:
            result += bytes([0x80 | bits])
            bits = value & 0x7f
            value >>= 7
        return result + bytes([bits])

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

    async def _execute_action(self, action, keypair, sign_func):
        """执行Protobuf Action"""
        # 序列化Action
        payload = action.SerializeToString()

        # 添加长度前缀
        length_prefix = self._encode_varint(len(payload))
        message = length_prefix + payload

        # 签名（包含长度前缀）
        signature = sign_func(message)

        # 组装最终数据
        final_data = message + signature

        # 发送请求
        async with self.session.post(
            f"{self.api_url}/action",
            data=final_data,
            headers={'Content-Type': 'application/octet-stream'}
        ) as resp:
            response_data = await resp.read()

            if resp.status != 200:
                logger.error(f"HTTP错误: {resp.status}")
                raise RuntimeError(f"HTTP {resp.status}")

            # 解析返回的Receipt（去掉varint前缀）
            if len(response_data) > 0:
                # 解码varint长度
                msg_len, pos = self._decode_varint(response_data, 0)
                actual_data = response_data[pos:pos + msg_len]

                receipt = schema_pb2.Receipt()
                receipt.ParseFromString(actual_data)

                return receipt
            else:
                raise RuntimeError("Empty response")

    # ==================== 订单操作 ====================

    async def place_order(
        self,
        market_id: int,
        side: str,  # 'buy' or 'sell'
        price: float,
        size: float,
        fill_mode: str = 'limit',  # 'limit', 'post_only', or 'immediate'
        is_reduce_only: bool = False
    ) -> Optional[int]:
        """
        下限价单

        Args:
            market_id: 市场ID（BTCUSD=0）
            side: 'buy' 或 'sell'
            price: 价格
            size: 数量
            fill_mode: 'limit', 'post_only', 或 'immediate'
            is_reduce_only: 是否只减仓

        Returns:
            order_id if success, None otherwise
        """
        if not schema_pb2:
            raise RuntimeError("schema_pb2 not available")

        await self._check_session_validity()

        server_time = await self.get_server_time()
        nonce = int(time.time() * 1000) % 1000000

        # 价格精度处理
        raw_price = int(price * (10 ** self._price_decimals))
        raw_size = int(size * (10 ** self._size_decimals))

        # 构建PlaceOrder消息
        action = schema_pb2.Action()
        action.current_timestamp = server_time
        action.nonce = nonce

        action.place_order.session_id = self.trading_session_id
        action.place_order.market_id = market_id
        action.place_order.side = schema_pb2.BID if side.lower() == 'buy' else schema_pb2.ASK

        # 设置订单模式
        if fill_mode == 'post_only':
            action.place_order.fill_mode = schema_pb2.POST_ONLY
        elif fill_mode == 'immediate':
            action.place_order.fill_mode = schema_pb2.IMMEDIATE_OR_CANCEL
        else:
            action.place_order.fill_mode = schema_pb2.LIMIT

        action.place_order.is_reduce_only = is_reduce_only
        action.place_order.price = raw_price
        action.place_order.size = raw_size

        try:
            receipt = await self._execute_action(action, self.session_keypair, self._session_sign)

            if receipt.HasField("err"):
                error_name = schema_pb2.Error.Name(receipt.err)

                # 会话过期，自动重建
                if 'SESSION' in error_name:
                    logger.warning("⚠️ 会话过期，重新创建...")
                    self.trading_session_id = None
                    await self._create_trading_session()
                    return await self.place_order(market_id, side, price, size, fill_mode, is_reduce_only)

                logger.error(f"下单失败: {error_name}")
                return None

            # 提取order_id - order_id在posted字段里面
            order_id = None

            if receipt.HasField("place_order_result"):
                # order_id在posted嵌套字段中
                if receipt.place_order_result.HasField("posted"):
                    order_id = receipt.place_order_result.posted.order_id
                    logger.debug(f"成功从posted中提取order_id: {order_id}")
                else:
                    logger.error(f"place_order_result中没有posted字段")
                    return None

            if order_id:
                # 保存到本地跟踪
                self._local_orders[order_id] = {
                    'order_id': order_id,
                    'price': price,
                    'size': size,
                    'side': side,
                    'market_id': market_id,
                    'time': time.time(),
                }
                logger.info(f"✅ 下单成功: {side} {size} @ ${price} (ID: {order_id})")

            return order_id

        except Exception as e:
            logger.error(f"下单异常: {e}")
            return None

    async def cancel_order(self, order_id: int, market_id: int = 0) -> str:
        """
        取消订单

        Args:
            order_id: 订单ID
            market_id: 市场ID

        Returns:
            'cancelled': 订单成功取消
            'filled': 订单已成交（ORDER_NOT_FOUND）
            'error': 撤单失败
        """
        if not schema_pb2:
            raise RuntimeError("schema_pb2 not available")

        await self._check_session_validity()

        server_time = await self.get_server_time()
        nonce = int(time.time() * 1000) % 1000000

        # 构建CancelOrderById消息
        action = schema_pb2.Action()
        action.current_timestamp = server_time
        action.nonce = nonce
        action.cancel_order_by_id.session_id = self.trading_session_id
        action.cancel_order_by_id.order_id = order_id

        try:
            receipt = await self._execute_action(action, self.session_keypair, self._session_sign)

            if receipt.HasField("err"):
                error_name = schema_pb2.Error.Name(receipt.err)

                # ORDER_NOT_FOUND = 订单已成交！
                if 'NOT_FOUND' in error_name:
                    logger.info(f"✅ 订单 {order_id} 已成交")
                    if order_id in self._local_orders:
                        del self._local_orders[order_id]
                    return 'filled'

                # 会话过期
                if 'SESSION' in error_name:
                    logger.warning("⚠️ 会话过期，重新创建...")
                    self.trading_session_id = None
                    await self._create_trading_session()
                    return await self.cancel_order(order_id, market_id)

                logger.error(f"撤单失败: {error_name}")
                return 'error'

            # 成功撤单
            if order_id in self._local_orders:
                del self._local_orders[order_id]

            logger.info(f"✅ 撤单成功: order_id={order_id}")
            return 'cancelled'

        except Exception as e:
            logger.error(f"撤单异常: {e}")
            return 'error'

    async def cancel_all_orders(self, market_id: int = 0) -> int:
        """
        取消所有订单

        Returns:
            取消的订单数量
        """
        order_ids = list(self._local_orders.keys())
        count = 0

        for order_id in order_ids:
            if await self.cancel_order(order_id, market_id):
                count += 1
            await asyncio.sleep(0.5)  # 防止过快

        logger.info(f"✅ 已取消 {count} 个订单")
        return count

    # ==================== 本地订单跟踪 ====================

    def get_local_orders(self, side: Optional[str] = None) -> List[Dict]:
        """
        获取本地跟踪的订单

        Args:
            side: 'buy', 'sell' 或 None（全部）

        Returns:
            订单列表
        """
        if side:
            return [o for o in self._local_orders.values() if o['side'] == side]
        return list(self._local_orders.values())

    def get_local_order_prices(self, side: str) -> List[float]:
        """获取本地订单的价格列表"""
        orders = self.get_local_orders(side)
        return sorted([o['price'] for o in orders])
