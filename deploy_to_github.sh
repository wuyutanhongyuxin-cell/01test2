#!/bin/bash

# 01exchange Grid Trading Bot - GitHub部署脚本
# 使用说明：chmod +x deploy_to_github.sh && ./deploy_to_github.sh

echo "==================================================="
echo "01exchange Grid Trading Bot - GitHub部署脚本"
echo "==================================================="

# 检查是否已经初始化git
if [ ! -d ".git" ]; then
    echo "初始化Git仓库..."
    git init
    git add .
    git commit -m "Initial commit: 01exchange Grid Trading Bot"
fi

echo ""
echo "请选择部署方式："
echo "1) 创建新的GitHub仓库（推荐）"
echo "2) 推送到现有仓库"
read -p "请输入选项 (1/2): " choice

if [ "$choice" = "1" ]; then
    echo ""
    read -p "请输入新仓库名称 (例如: 01exchange-grid-bot): " repo_name
    read -p "请输入你的GitHub用户名: " username

    echo ""
    echo "请按以下步骤操作："
    echo ""
    echo "1. 访问 https://github.com/new"
    echo "2. 创建名为 '$repo_name' 的新仓库"
    echo "3. 不要添加 README, .gitignore 或 license（我们已经有了）"
    echo "4. 创建完成后，返回此处按回车继续..."
    read -p ""

    # 添加远程仓库并推送
    git remote add origin "https://github.com/$username/$repo_name.git"
    git branch -M main
    git push -u origin main

    echo ""
    echo "✅ 部署完成！"
    echo "仓库地址: https://github.com/$username/$repo_name"

elif [ "$choice" = "2" ]; then
    echo ""
    read -p "请输入GitHub仓库完整URL (例如: https://github.com/user/repo.git): " repo_url

    # 检查是否已有remote
    if git remote | grep -q "origin"; then
        git remote set-url origin "$repo_url"
    else
        git remote add origin "$repo_url"
    fi

    git branch -M main
    git push -u origin main

    echo ""
    echo "✅ 推送完成！"
else
    echo "无效选项，退出。"
    exit 1
fi

echo ""
echo "==================================================="
echo "部署成功！接下来："
echo "1. 在VPS上克隆仓库"
echo "2. 配置 .env 文件"
echo "3. 运行 python main.py"
echo "==================================================="
