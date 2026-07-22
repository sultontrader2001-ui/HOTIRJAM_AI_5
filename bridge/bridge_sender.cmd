@echo off
REM Windows launcher — works even when Scripts\ is not on PATH.
REM Usage: bridge_sender.cmd --help
setlocal
set "BRIDGE_ROOT=%~dp0"
cd /d "%BRIDGE_ROOT%"
where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.13+ and retry.
    exit /b 1
  )
  py -3 -m hotirjam_bridge.sender %*
  exit /b %ERRORLEVEL%
)
python -m hotirjam_bridge.sender %*
exit /b %ERRORLEVEL%
