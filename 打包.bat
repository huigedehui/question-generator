@echo off
echo ========================================
echo    打包 AI 题库生成器 v1.0.0
echo ========================================
echo.

set APP_NAME=AI题库生成器
set VERSION=1.0.0
set ZIP_NAME=%APP_NAME%_v%VERSION%.zip

echo 正在创建压缩包...
powershell -Command "Compress-Archive -Path 'app.py','main.py','modules','templates','tests','docs','README.md','CHANGELOG.md','requirements.txt','setup.py','.gitignore','启动.bat','启动.sh' -DestinationPath '..\%ZIP_NAME%' -Force"

echo.
echo 打包完成: ..\%ZIP_NAME%
echo.
pause