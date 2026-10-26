@echo off
rem Baut die portable Windows-App: dist\3DGmax\3DGmax.exe und dist\3DGmax-<version>-Windows-x64.zip
rem Voraussetzung: pixi (https://pixi.sh). Aufruf mit --ohne-tests (oder DG_OHNE_TESTS=1): ohne Testlauf.
setlocal
cd /d "%~dp0\.."
call pixi install || exit /b 1
if "%1"=="--ohne-tests" set DG_OHNE_TESTS=1
if "%DG_OHNE_TESTS%"=="1" (
  echo Tests uebersprungen
) else (
  call pixi run test || exit /b 1
)
if exist build\pyinstaller rmdir /s /q build\pyinstaller
if exist dist\3DGmax rmdir /s /q dist\3DGmax
call pixi run bauen || exit /b 1
for /f %%v in ('pixi run python -c "from programm.version import VERSION; print(VERSION)"') do set VER=%%v
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\3DGmax -DestinationPath dist\3DGmax-%VER%-Windows-x64.zip" || exit /b 1
dist\3DGmax\3DGmax.exe --selbsttest || exit /b 1
echo Fertig: dist\3DGmax\3DGmax.exe und dist\3DGmax-%VER%-Windows-x64.zip
