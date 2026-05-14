@echo off
title AI Question Generator
cd /d "%~dp0"

echo ========================================
echo    AI Question Generator v1.0.0
echo ========================================
echo.

echo [1/3] Starting ngrok tunnel...
start /B ngrok\ngrok.exe http 5000 --log=stdout > NUL 2>&1

echo [2/3] Getting public URL...
powershell -Command ^
$retry=0; ^
while($retry -lt 5) { ^
  try { ^
    Start-Sleep -Seconds 2; ^
    $r=Invoke-RestMethod 'http://127.0.0.1:4040/api/tunnels' -ErrorAction Stop; ^
    Write-Host ('    Public URL: '+$r.tunnels[0].public_url); ^
    $retry=99; ^
    break; ^
  } catch { ^
    Write-Host ('    Waiting for ngrok... ('+$retry+')'); ^
    $retry++; ^
  } ^
} ^
if($retry -eq 5){Write-Host '    Public URL: (ngrok not ready, open http://localhost:5000 directly)'}

echo ========================================
echo.

echo [3/3] Starting Web server...
python app.py

pause