@echo off
cd /d "%~dp0"
echo NURION Presentation Character v0
echo.
set FAST06_PORT=8766
echo Open debug morph probe: http://127.0.0.1:8766/?debug=morph
echo Open presentation:      http://127.0.0.1:8766
echo Press Ctrl+C to stop.
echo.
py -3 tools\run_fast_06_presentation_server.py
