@echo off
title Khoidong Lean Teamwork Goose
cd /d "%~dp0"

echo ============================================================
echo   KHOI DONG LEAN TEAMWORK + DESKTOP WIDGET HUD CHO GOOSE
echo ============================================================
echo.

echo [1/2] Dang khoi dong Desktop Widget HUD...
powershell -ExecutionPolicy Bypass -File ".\widget\KHOI_DONG_WIDGET.ps1"

echo [2/2] Dang kich hoat Goose Session voi Lean Teamwork Protocol...
echo.
echo [PASS] Lean Teamwork Protocol da tu dong neo vao file .goosehints!
echo [PASS] Desktop Widget HUD dang chay noi ngoai man hinh.
echo.

goose session
