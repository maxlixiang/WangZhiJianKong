@echo off
:: 强制使用 UTF-8 编码，防止中文乱码
chcp 65001 >nul
SETLOCAL Enabledelayedexpansion

echo =======================================
echo    🚀 YunyouJianKong 一键同步工具
echo =======================================

:: 安全检查：检查是否误带了敏感文件
set "danger=0"
for %%f in (.env tasks.json stock_state.json) do (
    git status --short | findstr "%%f" >nul
    if !errorlevel! equ 0 (
        echo [❌ 警报] 发现敏感文件 %%f 在提交列表中！
        set "danger=1"
    )
)

if "!danger!"=="1" (
    echo [!] 请检查 .gitignore 是否配置正确。
    echo [!] 同步已终止，保护您的 Token 安全。
    pause
    exit /b
)

echo [1/3] 准备打包修改内容...
git add .

set /p msg="请输入更新说明 (直接回车使用时间戳): "
if "%msg%"=="" set msg=Update %date% %time%

echo [2/3] 正在本地提交: %msg%
git commit -m "%msg%"

echo [3/3] 正在推送到 GitHub...
git push

echo =======================================
echo ✅ 同步完成！您的代码已上云。
echo =======================================
pause