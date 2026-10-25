@echo off
title Proposed Network Monitoring System (http://127.0.0.1:8001)
cd /d "%~dp0"
echo ========================================================
echo Starting Unified Proposed Network Monitoring System...
echo Web Application: http://127.0.0.1:8001
echo (Python ICMP and ML Engine merged in background on 5001)
echo ========================================================
echo.
call npm run dev:all
pause
