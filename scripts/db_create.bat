@echo off
chcp 65001 >nul
echo ========================================
echo 数据库创建脚本
echo ========================================
echo 说明: 创建新数据库，不修改原数据库
echo ========================================
echo.

cd /d "%~dp0.."

set /p new_db="请输入新数据库名称: "

if "%new_db%"=="" (
    echo 数据库名称不能为空
    pause
    exit /b 1
)

echo.
echo 新数据库名称: %new_db%
echo.
echo 请选择数据初始化模式:
echo [1] 全新初始化 - 创建默认管理员用户(admin/admin123)、角色、关键词
echo [2] 从原数据库复制 - 复制原数据库的基础配置数据
echo [3] 仅创建表结构 - 不初始化任何数据
echo [4] 模拟运行 - 预览执行计划（全新初始化）
echo [5] 退出
echo.

set /p choice="请输入选项 (1/2/3/4/5): "

if "%choice%"=="1" (
    echo.
    echo 执行全新初始化...
    echo 默认管理员: admin / admin123
    echo.
    python scripts\db_create.py --new-db %new_db% --init-data
) else if "%choice%"=="2" (
    echo.
    echo 从原数据库复制基础数据...
    python scripts\db_create.py --new-db %new_db% --copy-from-source
) else if "%choice%"=="3" (
    echo.
    echo 仅创建表结构...
    python scripts\db_create.py --new-db %new_db%
) else if "%choice%"=="4" (
    echo.
    echo 模拟运行...
    python scripts\db_create.py --new-db %new_db% --init-data --dry-run
) else if "%choice%"=="5" (
    echo 已退出
) else (
    echo 无效选项
)

echo.
pause