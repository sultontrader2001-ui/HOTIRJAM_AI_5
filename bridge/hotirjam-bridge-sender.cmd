@echo off
REM Alias for bridge_sender.cmd
call "%~dp0bridge_sender.cmd" %*
exit /b %ERRORLEVEL%
