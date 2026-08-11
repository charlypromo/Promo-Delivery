@echo off
title Promo Delivery V4
cd /d %~dp0
where python >nul 2>&1
if errorlevel 1 (
  echo Python pa enstale sou PC a.
  echo Enstale Python 3.11 oswa pi nouvo epi rekomanse.
  pause
  exit /b
)
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -r requirements.txt
echo.
echo ==========================================
echo PROMO DELIVERY AP KOURI
echo Ouvri: http://127.0.0.1:5000
echo Admin: http://127.0.0.1:5000/admin
echo Livreur: http://127.0.0.1:5000/driver
echo ==========================================
python app.py
pause
