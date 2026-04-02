@echo off
setlocal
cd /d "%~dp0"
echo === ResonantOS Installer (Phase 1: Detection) ===
node installer-entry.js
echo.
echo Done. Press any key to exit.
pause >nul
