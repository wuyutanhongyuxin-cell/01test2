# 🚀 部署到GitHub和VPS的完整指令

## ✅ 项目已创建完成

项目位置: `E:\ubuntu_test\01exchange-grid-bot`

## 📦 项目文件清单

```
01exchange-grid-bot/
├── config/
│   ├── __init__.py
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── api_client.py
│   ├── indicators.py
│   ├── order_tracker.py
│   ├── risk_manager.py
│   ├── grid_strategy.py
│   └── trader.py
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── QUICKSTART.md
├── VPS_DEPLOYMENT.md
├── PROJECT_SUMMARY.md
├── DEPLOY_INSTRUCTIONS.md (本文件)
├── deploy_to_github.sh
├── deploy_to_github.bat
└── install_vps.sh
```

## 第一步：推送到GitHub

### 方法A：使用自动化脚本（推荐）

**Windows用户**:
```batch
cd E:\ubuntu_test\01exchange-grid-bot
deploy_to_github.bat
```

**Linux/Mac用户**:
```bash
cd /e/ubuntu_test/01exchange-grid-bot
chmod +x deploy_to_github.sh
./deploy_to_github.sh
```

### 方法B：手动推送

1. **在GitHub创建新仓库**
   - 访问: https://github.com/new
   - 仓库名: `01exchange-grid-bot` (或你喜欢的名字)
   - 设为Public或Private
   - ⚠️ **不要**勾选"Add a README file"
   - 点击"Create repository"

2. **推送代码**

```bash
# 进入项目目录
cd E:\ubuntu_test\01exchange-grid-bot

# 添加远程仓库（替换YOUR_USERNAME为你的GitHub用户名）
git remote add origin https://github.com/YOUR_USERNAME/01exchange-grid-bot.git

# 推送代码
git branch -M main
git push -u origin main
```

3. **验证推送成功**
   - 访问: https://github.com/YOUR_USERNAME/01exchange-grid-bot
   - 应该能看到所有文件

## 第二步：在VPS上部署

### 前置条件

- 准备一台VPS（Ubuntu 20.04+推荐）
- 获取VPS的IP地址和SSH登录信息
- 准备好Solana钱包私钥

### 部署步骤

1. **SSH连接到VPS**

```bash
ssh your_username@your_vps_ip
```

2. **克隆你的GitHub仓库**

```bash
# 替换YOUR_USERNAME为你的GitHub用户名
git clone https://github.com/YOUR_USERNAME/01exchange-grid-bot.git
cd 01exchange-grid-bot
```

3. **运行一键安装脚本**

```bash
chmod +x install_vps.sh
./install_vps.sh
```

脚本会自动：
- ✅ 更新系统
- ✅ 安装Python 3和依赖
- ✅ 创建虚拟环境
- ✅ 安装Python包
- ✅ 下载并编译Protobuf
- ✅ 创建配置文件

4. **配置环境变量**

```bash
nano .env
```

修改以下关键配置：

```ini
# 你的Solana私钥（必须修改！）
SOLANA_PRIVATE_KEY=your_actual_private_key_here

# API地址（主网/测试网）
API_URL=https://zo-mainnet.n1.xyz
# API_URL=https://zo-devnet.n1.xyz  # 建议先用测试网

# 其他参数根据需要调整
TOTAL_ORDERS=18
WINDOW_PERCENT=0.12
MAX_MULTIPLIER=15
```

保存并退出（Ctrl+O, Enter, Ctrl+X）

5. **测试运行**

```bash
# 激活虚拟环境
source venv/bin/activate

# 启动程序（测试）
python main.py
```

如果看到类似输出，说明成功：

```
============================================
01exchange Grid Trading Bot
============================================
API地址: https://zo-mainnet.n1.xyz
交易对: BTCUSD (Market ID: 0)
✅ 已连接到 https://zo-mainnet.n1.xyz
============================================
```

按 Ctrl+C 停止测试。

6. **后台运行（生产环境）**

**使用Screen（推荐）:**

```bash
# 安装screen
sudo apt install screen -y

# 创建新会话
screen -S gridbot

# 激活虚拟环境并运行
source venv/bin/activate
python main.py

# 按 Ctrl+A 然后按 D 分离会话（程序继续运行）

# 重新连接
screen -r gridbot

# 查看所有会话
screen -ls
```

**使用Systemd服务（更稳定）:**

查看详细说明: [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md#方法3-使用systemd服务生产环境推荐)

## 第三步：监控和维护

### 查看日志

```bash
# 实时查看
tail -f grid_trader.log

# 查看最近100行
tail -n 100 grid_trader.log

# 搜索错误
grep "ERROR" grid_trader.log
```

### 检查运行状态

```bash
# 如果使用screen
screen -ls

# 如果使用systemd
sudo systemctl status gridbot
```

### 停止程序

```bash
# 如果在screen中
screen -r gridbot
# 然后按 Ctrl+C

# 如果使用systemd
sudo systemctl stop gridbot
```

## 🎯 快速命令参考

### GitHub相关

```bash
# 查看远程仓库
git remote -v

# 更新代码到GitHub
git add .
git commit -m "Update configuration"
git push

# 从GitHub拉取最新代码
git pull
```

### VPS相关

```bash
# SSH连接
ssh user@vps_ip

# 进入项目目录
cd ~/01exchange-grid-bot

# 激活虚拟环境
source venv/bin/activate

# 启动程序
python main.py

# 后台运行（screen）
screen -S gridbot
source venv/bin/activate
python main.py
# Ctrl+A D

# 重新连接
screen -r gridbot

# 查看日志
tail -f grid_trader.log

# 更新代码
git pull
sudo systemctl restart gridbot  # 如果使用systemd
```

## 📚 相关文档

- **完整使用说明**: [README.md](README.md)
- **快速开始**: [QUICKSTART.md](QUICKSTART.md)
- **VPS部署详解**: [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md)
- **项目总结**: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)

## ⚠️ 重要提醒

1. **先测试网测试**:
   - 修改 `.env` 中的 `API_URL=https://zo-devnet.n1.xyz`
   - 充分测试后再切换到主网

2. **保护私钥**:
   - 不要将 `.env` 提交到GitHub
   - 确保 `.env` 权限是 600: `chmod 600 .env`

3. **监控运行**:
   - 前几天要经常查看日志
   - 关注风控冷却触发情况
   - 检查订单执行是否正常

4. **风险控制**:
   - 初始仓位不要太大
   - 设置合理的 `MAX_MULTIPLIER`
   - 及时调整参数

## 🆘 遇到问题？

### 常见问题

1. **schema_pb2 not found**
   ```bash
   curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto
   protoc --python_out=. schema.proto
   ```

2. **Permission denied**
   ```bash
   chmod +x install_vps.sh deploy_to_github.sh
   ```

3. **ModuleNotFoundError**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Git推送失败**
   ```bash
   # 检查远程仓库
   git remote -v

   # 设置正确的远程仓库
   git remote set-url origin https://github.com/YOUR_USERNAME/01exchange-grid-bot.git
   ```

### 获取帮助

- 查看 [README.md](README.md) 的故障排除章节
- 查看 [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md) 的故障排除章节
- GitHub Issues: 提交问题到你的仓库

## ✅ 验证清单

部署前请确认：

- [ ] 已在GitHub创建仓库
- [ ] 代码已成功推送到GitHub
- [ ] VPS可以正常SSH连接
- [ ] Python 3.8+ 已安装
- [ ] Protobuf已编译 (`schema_pb2.py`存在)
- [ ] `.env`文件已配置正确的私钥
- [ ] 先在测试网测试成功
- [ ] 了解风控机制和风险

## 🎉 部署成功！

如果一切顺利，你现在应该有：

✅ 代码托管在GitHub
✅ VPS上程序正常运行
✅ 日志正常记录
✅ 风控机制工作正常

接下来：

1. 监控日志输出
2. 观察订单执行
3. 根据市场调整参数
4. 定期检查系统状态

**祝交易顺利！🚀**

---

**最后更新**: 2026-02-01
**创建者**: Claude AI
