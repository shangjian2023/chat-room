@echo off
chcp 65001 >nul
echo ========================================
echo     课程平台 - 启动脚本
echo ========================================
echo.

echo [1/3] 初始化数据库...
python setup_database.py
if errorlevel 1 (
    echo.
    echo ! 数据库初始化失败，请检查 MySQL 安装
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] 启动 Flask 服务器...
echo.
echo 服务器地址：http://localhost:8080
echo 局域网访问：http://你的 IP:8080
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

python app.py
