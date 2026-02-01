# VPS部署指南

本文档详细说明如何在VPS上部署01exchange Grid Trading Bot。

## 📋 前置要求

- VPS系统：Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- Python 3.8+
- 至少 512MB RAM
- 稳定的网络连接

## 🚀 快速部署（推荐）

### 1. 连接到VPS

```bash
ssh your_username@your_vps_ip
```

### 2. 安装依赖

**Ubuntu/Debian:**

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python和必要工具
sudo apt install -y python3 python3-pip python3-venv git protobuf-compiler

# 验证安装
python3 --version  # 应该 >= 3.8
protoc --version   # 应该有输出
```

**CentOS/RHEL:**

```bash
# 更新系统
sudo yum update -y

# 安装Python和必要工具
sudo yum install -y python3 python3-pip git protobuf-compiler

# 或者使用 dnf (CentOS 8+)
sudo dnf install -y python3 python3-pip git protobuf-compiler
```

### 3. 克隆仓库

```bash
# 克隆你的GitHub仓库
git clone https://github.com/YOUR_USERNAME/01exchange-grid-bot.git
cd 01exchange-grid-bot
```

### 4. 设置Python虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级pip
pip install --upgrade pip
```

### 5. 安装Python依赖

```bash
pip install -r requirements.txt
```

如果安装失败，尝试：

```bash
# 如果某些包安装失败，单独安装
pip install aiohttp python-dotenv protobuf solders pandas numpy ccxt
```

### 6. 下载并编译Protobuf Schema

```bash
# 下载schema文件（主网）
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto

# 编译为Python
protoc --python_out=. schema.proto

# 验证生成
ls -lh schema_pb2.py
```

### 7. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件
nano .env
```

**重要配置项**：

```ini
# API地址
API_URL=https://zo-mainnet.n1.xyz

# 你的Solana私钥（Base58格式）
SOLANA_PRIVATE_KEY=your_private_key_here_replace_this

# 交易参数
TOTAL_ORDERS=18
WINDOW_PERCENT=0.12
MAX_MULTIPLIER=15

# 风控参数
RSI_MIN=30
RSI_MAX=70
ADX_TREND_THRESHOLD=25
ADX_STRONG_TREND=30
```

保存并退出（Ctrl+O, Enter, Ctrl+X）

### 8. 测试运行

```bash
# 先测试一下是否能正常启动
python main.py
```

如果看到类似输出，说明成功：

```
2026-02-01 10:30:15 [INFO] __main__: ============================================
2026-02-01 10:30:15 [INFO] __main__: 01exchange Grid Trading Bot
2026-02-01 10:30:15 [INFO] __main__: ============================================
2026-02-01 10:30:15 [INFO] api_client: ✅ 已连接到 https://zo-mainnet.n1.xyz
```

按 Ctrl+C 停止测试。

## 🔄 使用Screen/Tmux保持后台运行

### 方法1: 使用Screen（推荐）

```bash
# 安装screen
sudo apt install screen  # Ubuntu/Debian
sudo yum install screen  # CentOS

# 创建新的screen会话
screen -S gridbot

# 激活虚拟环境并运行
cd ~/01exchange-grid-bot
source venv/bin/activate
python main.py

# 按 Ctrl+A 然后按 D 来分离会话（程序继续运行）

# 重新连接到会话
screen -r gridbot

# 查看所有会话
screen -ls

# 终止会话
screen -X -S gridbot quit
```

### 方法2: 使用Tmux

```bash
# 安装tmux
sudo apt install tmux  # Ubuntu/Debian

# 创建新会话
tmux new -s gridbot

# 激活虚拟环境并运行
cd ~/01exchange-grid-bot
source venv/bin/activate
python main.py

# 按 Ctrl+B 然后按 D 来分离会话

# 重新连接
tmux attach -t gridbot

# 查看所有会话
tmux ls
```

### 方法3: 使用Systemd服务（生产环境推荐）

创建systemd服务文件：

```bash
sudo nano /etc/systemd/system/gridbot.service
```

内容：

```ini
[Unit]
Description=01exchange Grid Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/01exchange-grid-bot
Environment="PATH=/home/your_username/01exchange-grid-bot/venv/bin"
ExecStart=/home/your_username/01exchange-grid-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**替换以下内容**：
- `your_username` → 你的VPS用户名
- `/home/your_username/01exchange-grid-bot` → 实际路径

启动服务：

```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start gridbot

# 设置开机自启
sudo systemctl enable gridbot

# 查看状态
sudo systemctl status gridbot

# 查看日志
sudo journalctl -u gridbot -f

# 停止服务
sudo systemctl stop gridbot
```

## 📊 监控和日志

### 查看日志

```bash
# 实时查看日志
tail -f grid_trader.log

# 查看最近100行
tail -n 100 grid_trader.log

# 搜索错误
grep "ERROR" grid_trader.log

# 查看今天的日志
grep "$(date +%Y-%m-%d)" grid_trader.log
```

### 日志管理

创建日志轮转配置：

```bash
sudo nano /etc/logrotate.d/gridbot
```

内容：

```
/home/your_username/01exchange-grid-bot/grid_trader.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    create 0644 your_username your_username
}
```

## 🔒 安全建议

### 1. 保护私钥

```bash
# 确保.env文件权限正确
chmod 600 .env

# 不要将.env文件提交到GitHub
cat .gitignore | grep ".env"  # 应该看到 .env
```

### 2. 配置防火墙

```bash
# Ubuntu/Debian
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# CentOS
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 3. 定期更新

```bash
# 更新代码
cd ~/01exchange-grid-bot
git pull

# 重启服务
sudo systemctl restart gridbot  # 如果使用systemd

# 或者重新启动screen会话
screen -X -S gridbot quit
screen -S gridbot
source venv/bin/activate
python main.py
# Ctrl+A D 分离
```

## 🛠️ 故障排除

### 问题1: ModuleNotFoundError

```bash
# 确保虚拟环境已激活
source venv/bin/activate

# 重新安装依赖
pip install -r requirements.txt
```

### 问题2: protobuf错误

```bash
# 重新编译
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto
protoc --python_out=. schema.proto
```

### 问题3: 内存不足

```bash
# 检查内存
free -h

# 如果内存不足，创建swap
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久启用
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 问题4: 连接超时

```bash
# 测试网络连接
ping -c 3 zo-mainnet.n1.xyz
curl -I https://zo-mainnet.n1.xyz

# 检查DNS
cat /etc/resolv.conf
```

### 问题5: 进程意外退出

```bash
# 查看系统日志
sudo journalctl -xe

# 查看程序日志
tail -f grid_trader.log

# 如果使用systemd，查看服务日志
sudo journalctl -u gridbot -n 50
```

## 📈 性能优化

### 1. 调整系统参数

```bash
# 编辑limits
sudo nano /etc/security/limits.conf

# 添加：
* soft nofile 65536
* hard nofile 65536
```

### 2. 使用更快的DNS

```bash
sudo nano /etc/resolv.conf

# 添加Google DNS
nameserver 8.8.8.8
nameserver 8.8.4.4
```

### 3. 启用BBR拥塞控制

```bash
# 检查内核版本（需要4.9+）
uname -r

# 启用BBR
echo "net.core.default_qdisc=fq" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## 🔔 告警和通知

### 设置邮件告警（可选）

安装mailutils：

```bash
sudo apt install mailutils
```

修改main.py添加错误通知：

```python
import smtplib
from email.message import EmailMessage

def send_alert(subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = 'your_email@gmail.com'
    msg['To'] = 'your_email@gmail.com'

    # 使用Gmail SMTP
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login('your_email@gmail.com', 'your_app_password')
        smtp.send_message(msg)
```

## 📝 定期维护

### 每日检查

```bash
# 检查服务状态
systemctl status gridbot

# 查看最新日志
tail -n 50 ~/01exchange-grid-bot/grid_trader.log
```

### 每周检查

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 检查磁盘空间
df -h

# 清理旧日志（如果没有logrotate）
find ~/01exchange-grid-bot -name "*.log" -mtime +7 -delete
```

### 每月检查

```bash
# 拉取最新代码
cd ~/01exchange-grid-bot
git pull

# 重启服务
sudo systemctl restart gridbot
```

## 📞 支持

如果遇到问题：

1. 查看 README.md 的故障排除章节
2. 检查 grid_trader.log 日志文件
3. 在GitHub提交Issue
4. 加入社区讨论

---

**提示**: 建议先在测试网运行几天，确认稳定后再用于主网实盘交易。
