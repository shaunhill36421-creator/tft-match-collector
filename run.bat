@echo off
REM ============================================================
REM  TFT Match Collector - file chay nhanh tren Windows
REM  (Bam dup vao file nay de chay. Ghi chu khong dau de tranh loi font.)
REM ============================================================

REM Bat UTF-8 de phan tieng Viet do Python in ra hien thi dung.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM Luon chay tu dung thu muc chua file .bat nay.
cd /d "%~dp0"

echo.
echo ============================================
echo    TFT MATCH COLLECTOR
echo ============================================
echo.

REM --- Buoc 1: Kiem tra Python da cai chua ---
where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python tren may.
    echo.
    echo  Hay cai Python 3.10 tro len tai: https://www.python.org/downloads/
    echo  QUAN TRONG: khi cai, nho TICH chon "Add Python to PATH".
    echo  Cai xong, mo lai file run.bat nay.
    echo.
    pause
    exit /b 1
)

REM --- Buoc 2: Cai thu vien can thiet (requests) neu thieu ---
echo Dang kiem tra / cai thu vien can thiet (requests)...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [CANH BAO] Cai thu vien gap loi. Thu chay lai, hoac kiem tra Internet.
    echo.
)

REM --- Buoc 3: Chay chuong trinh chinh ---
echo.
python src\main.py
echo.

REM Giu cua so mo de doc ket qua.
pause
