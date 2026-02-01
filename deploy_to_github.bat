@echo off
chcp 65001 >nul
echo ===================================================
echo 01exchange Grid Trading Bot - GitHub部署脚本
echo ===================================================
echo.

REM 检查是否已经初始化git
if not exist ".git" (
    echo 初始化Git仓库...
    git init
    git add .
    git commit -m "Initial commit: 01exchange Grid Trading Bot"
)

echo.
echo 请选择部署方式：
echo 1^) 创建新的GitHub仓库（推荐）
echo 2^) 推送到现有仓库
set /p choice="请输入选项 (1/2): "

if "%choice%"=="1" (
    echo.
    set /p repo_name="请输入新仓库名称 (例如: 01exchange-grid-bot): "
    set /p username="请输入你的GitHub用户名: "

    echo.
    echo 请按以下步骤操作：
    echo.
    echo 1. 访问 https://github.com/new
    echo 2. 创建名为 '%repo_name%' 的新仓库
    echo 3. 不要添加 README, .gitignore 或 license（我们已经有了）
    echo 4. 创建完成后，返回此处按任意键继续...
    pause >nul

    REM 添加远程仓库并推送
    git remote add origin https://github.com/%username%/%repo_name%.git
    git branch -M main
    git push -u origin main

    echo.
    echo ✅ 部署完成！
    echo 仓库地址: https://github.com/%username%/%repo_name%

) else if "%choice%"=="2" (
    echo.
    set /p repo_url="请输入GitHub仓库完整URL (例如: https://github.com/user/repo.git): "

    REM 检查是否已有remote
    git remote | findstr "origin" >nul
    if errorlevel 1 (
        git remote add origin %repo_url%
    ) else (
        git remote set-url origin %repo_url%
    )

    git branch -M main
    git push -u origin main

    echo.
    echo ✅ 推送完成！
) else (
    echo 无效选项，退出。
    exit /b 1
)

echo.
echo ===================================================
echo 部署成功！接下来：
echo 1. 在VPS上克隆仓库
echo 2. 配置 .env 文件
echo 3. 运行 python main.py
echo ===================================================
pause
