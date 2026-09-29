@echo off
REM ============================================================
REM  dsh-forward launcher   (sibling of dsh-web.bat)
REM
REM  Runs `uv run --no-project forward.py --launch --qr --update-dsh`:
REM    0) reports the installed dsh version and upgrades it to the
REM       newest stable / RC on npm when one is newer,
REM    1) starts `dsh web --no-open` itself and captures its token URL,
REM    2) binds the LAN address on the same port, path-for-path,
REM    3) prints a scannable QR code in the terminal.
REM
REM  uv builds the environment from the PEP 723 block at the top of
REM  forward.py, so there is no venv to create by hand.
REM  --no-project matters: this folder sits inside a repo that has its
REM  own pyproject.toml, and without it uv would use that project.
REM
REM  Usage:  dsh-forward.bat [extra forward.py options]
REM          dsh-forward.bat --no-update-dsh
REM          dsh-forward.bat --qr-open
REM          dsh-forward.bat --no-open-browser
REM          dsh-forward.bat --port 8081
REM
REM  If the phone cannot connect, add the inbound rule once in an
REM  ADMIN PowerShell (the WLAN profile is usually "Public"):
REM    New-NetFirewallRule -DisplayName "dsh-forward 3080" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3080 -Profile Any
REM
REM  Encoding note: this file is UTF-8 WITHOUT BOM and uses CRLF.
REM  It is deliberately all-ASCII so the console codepage cannot
REM  mangle it; every Chinese message comes from Python instead.
REM ============================================================
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title dsh-forward
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 goto :no_uv

uv run --no-project "%~dp0forward.py" --launch --qr --update-dsh %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :failed

endlocal & exit /b 0

:no_uv
echo.
echo [ERROR] uv not found in PATH.
echo.
echo Install it once:
echo         winget install astral-sh.uv
echo   or    https://docs.astral.sh/uv/
echo.
echo Plain Python also works if you skip the QR code (segno is only
echo needed for it):
echo         py -3 "%~dp0forward.py" --launch
echo.
pause
endlocal & exit /b 1

:failed
echo.
echo [ERROR] forward.py exited with code %RC%
echo         Likely causes: port already in use, or dsh could not be found.
echo         Try: dsh-forward.bat --port 8081
echo.
pause
endlocal & exit /b %RC%
