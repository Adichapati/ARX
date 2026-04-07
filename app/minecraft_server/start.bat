@echo off
setlocal
cd /d %~dp0
if not exist eula.txt echo eula=true>eula.txt

where java >nul 2>nul
if errorlevel 1 (
  echo [ARX][ERROR] Java not found in PATH. Install Java 21+.
  exit /b 1
)

for /f "tokens=3" %%v in ('java -version 2^>^&1 ^| findstr /i "version"') do set JAVAVER=%%v
set JAVAVER=%JAVAVER:"=%
for /f "tokens=1 delims=." %%m in ("%JAVAVER%") do set MAJOR=%%m
if "%MAJOR%"=="1" (
  for /f "tokens=2 delims=." %%m in ("%JAVAVER%") do set MAJOR=%%m
)

if %MAJOR% LSS 21 (
  echo [ARX][ERROR] Java 21+ required. Detected Java %JAVAVER%.
  echo Download: https://adoptium.net/temurin/releases/?version=21
  exit /b 1
)

java -Xms1G -Xmx2G -jar server.jar nogui
