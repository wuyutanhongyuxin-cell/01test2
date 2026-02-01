# 快速启动指南 ⚡

## 1分钟快速部署（本地测试）

### Windows用户

```batch
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/01exchange-grid-bot.git
cd 01exchange-grid-bot

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 下载并编译protobuf
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto
protoc --python_out=. schema.proto

# 5. 配置环境变量
copy .env.example .env
notepad .env  # 修改SOLANA_PRIVATE_KEY

# 6. 运行
python main.py
```

### Linux/Mac用户

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/01exchange-grid-bot.git
cd 01exchange-grid-bot

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 下载并编译protobuf
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto
protoc --python_out=. schema.proto

# 5. 配置环境变量
cp .env.example .env
nano .env  # 修改SOLANA_PRIVATE_KEY

# 6. 运行
python main.py
```

## 推送到GitHub

### 方法1: 使用部署脚本（推荐）

**Windows:**
```batch
deploy_to_github.bat
```

**Linux/Mac:**
```bash
chmod +x deploy_to_github.sh
./deploy_to_github.sh
```

### 方法2: 手动推送

```bash
# 1. 在GitHub创建新仓库（不要添加任何文件）

# 2. 添加远程仓库
git remote add origin https://github.com/YOUR_USERNAME/01exchange-grid-bot.git

# 3. 推送代码
git branch -M main
git push -u origin main
```

## VPS部署（推荐用于生产）

```bash
# 1. SSH连接到VPS
ssh user@your_vps_ip

# 2. 克隆仓库
git clone https://github.com/YOUR_USERNAME/01exchange-grid-bot.git
cd 01exchange-grid-bot

# 3. 运行一键安装脚本
chmod +x install_vps.sh
./install_vps.sh

# 4. 使用screen保持后台运行
screen -S gridbot
source venv/bin/activate
python main.py
# 按 Ctrl+A 然后按 D 分离会话
```

详细的VPS部署指南请查看 [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md)

## 常见问题

**Q: schema_pb2 not found 错误？**

A: 需要先编译protobuf文件：
```bash
curl -o schema.proto https://zo-mainnet.n1.xyz/schema.proto
protoc --python_out=. schema.proto
```

**Q: 如何获取Solana私钥？**

A: 使用solana-keygen工具：
```bash
solana-keygen new --outfile ~/my-keypair.json
# 私钥在JSON文件中
```

**Q: 如何在测试网运行？**

A: 修改.env文件：
```ini
API_URL=https://zo-devnet.n1.xyz
```

**Q: 如何停止程序？**

A: 按 `Ctrl+C` 即可安全停止。

**Q: 如何查看运行状态？**

A: 查看日志文件：
```bash
tail -f grid_trader.log
```

## 下一步

- 阅读完整文档: [README.md](README.md)
- VPS部署指南: [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md)
- 参数调优建议: 查看README.md的"参数调优"章节
- 风险提示: 务必先在测试网测试！

## 紧急停止

如果需要立即停止所有交易：

1. 按 `Ctrl+C` 停止程序
2. 程序会自动取消所有挂单
3. 如果是风控冷却触发，会先平仓再停止

## 技术支持

- GitHub Issues: https://github.com/YOUR_USERNAME/01exchange-grid-bot/issues
- 文档: 查看README.md
- 原作者Twitter: @ddazmon

---

**⚠️ 风险警告**: 请先在测试网充分测试，确认理解所有风险后再用于实盘交易！
