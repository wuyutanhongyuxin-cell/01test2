#!/bin/bash

# 01exchange Grid Trading Bot - VPS一键安装脚本
# 适用于 Ubuntu 20.04+ / Debian 11+

set -e  # 遇到错误立即退出

echo "=============================================="
echo "01exchange Grid Trading Bot - 一键安装"
echo "=============================================="
echo ""

# 检测系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
else
    echo "无法检测系统版本"
    exit 1
fi

echo "检测到系统: $OS $VER"
echo ""

# 更新系统
echo "[1/7] 更新系统..."
if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
    sudo apt update
    sudo apt upgrade -y
elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
    sudo yum update -y
fi

# 安装依赖
echo "[2/7] 安装依赖..."
if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
    sudo apt install -y python3 python3-pip python3-venv git curl protobuf-compiler
elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
    sudo yum install -y python3 python3-pip git curl protobuf-compiler
fi

# 验证Python版本
echo "[3/7] 验证Python版本..."
PYTHON_VERSION=$(python3 --version | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "错误: Python版本需要 >= 3.8，当前版本: $PYTHON_VERSION"
    exit 1
fi

echo "Python版本: $PYTHON_VERSION ✓"

# 创建虚拟环境
echo "[4/7] 创建Python虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装Python依赖
echo "[5/7] 安装Python依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 下载并编译Protobuf
echo "[6/7] 下载并编译Protobuf Schema..."
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto
protoc --python_out=. schema.proto

if [ ! -f "schema_pb2.py" ]; then
    echo "错误: Protobuf编译失败"
    exit 1
fi

echo "Protobuf编译成功 ✓"

# 配置环境变量
echo "[7/7] 配置环境变量..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  请编辑 .env 文件配置你的私钥:"
    echo "    nano .env"
    echo ""
    echo "必须配置项:"
    echo "  - SOLANA_PRIVATE_KEY (你的Solana钱包私钥)"
    echo ""
fi

# 安装完成
echo ""
echo "=============================================="
echo "✅ 安装完成！"
echo "=============================================="
echo ""
echo "下一步:"
echo ""
echo "1. 配置环境变量:"
echo "   nano .env"
echo ""
echo "2. 启动程序（测试）:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "3. 后台运行（推荐）:"
echo "   screen -S gridbot"
echo "   source venv/bin/activate"
echo "   python main.py"
echo "   # 按 Ctrl+A 然后按 D 分离会话"
echo ""
echo "4. 重新连接到后台会话:"
echo "   screen -r gridbot"
echo ""
echo "5. 查看日志:"
echo "   tail -f grid_trader.log"
echo ""
echo "=============================================="
echo "⚠️  风险警告: 请先在测试网测试！"
echo "=============================================="
