@echo off
REM cvforge launcher for Windows: double-click to install (first run) and open cvforge in your browser.
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(sys.version_info < (3, 11))" || goto nopython

if not exist ".venv\Scripts\cvforge.exe" (
  echo.
  echo   Setting up cvforge ^(first start takes 1-2 minutes^)...
  %PY% -m venv .venv || goto failed
  ".venv\Scripts\python" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python" -m pip install --quiet -e . || goto failed
)

if exist "C:\msys64\mingw64\bin" set "WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin"
".venv\Scripts\python" -c "import weasyprint" >nul 2>nul || goto nopango
".venv\Scripts\cvforge" start
goto end

:nopython
echo.
echo   cvforge needs Python 3.11 or newer.
echo   Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^), then run this again.
goto wait

:nopango
echo.
echo   One more thing: cvforge needs the GTK/Pango libraries to create PDFs.
echo   1. Install MSYS2 from https://www.msys2.org
echo   2. In the "MSYS2 MINGW64" window run:  pacman -S mingw-w64-x86_64-pango
echo   3. Start cvforge again.
echo   Details: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows
goto wait

:failed
echo.
echo   Installation failed - see the messages above.

:wait
echo.
pause
:end
endlocal
