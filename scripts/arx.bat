@echo off
setlocal
set ROOT=%~dp0..
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\scripts\arx_cli.py" %*
