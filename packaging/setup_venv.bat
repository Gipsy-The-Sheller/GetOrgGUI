@echo off
setlocal
set "ROOT=%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

%PY% -m venv "%ROOT%venv"
if errorlevel 1 goto :error

"%ROOT%venv\Scripts\python.exe" -m pip install --upgrade pip
"%ROOT%venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 goto :error

if exist "%ROOT%gui\requirements.txt" (
    "%ROOT%venv\Scripts\python.exe" -m pip install -r "%ROOT%gui\requirements.txt"
    if errorlevel 1 (
        echo.
        echo WARNING: GUI dependencies could not be installed.
        echo The command-line package still works; the desktop GUI may not start.
    )
)

echo.
echo Python environment created at "%ROOT%venv".
goto :eof

:error
echo.
echo Failed to create the Python environment. Install Python 3.10+ (64-bit)
echo and make sure "python" or "py" is available in PATH.
exit /b 1
