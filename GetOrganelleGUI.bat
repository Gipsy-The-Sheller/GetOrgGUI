@echo off
setlocal
set "ROOT=%~dp0"
set "PATH=%ROOT%venv\Scripts;%ROOT%GetOrganelle\GetOrganelleDep\Windows\bowtie2;%ROOT%GetOrganelle\GetOrganelleDep\Windows\ncbi-blast;%ROOT%GetOrganelle\GetOrganelleDep\Windows\SPAdes\bin;%PATH%"
if exist "%ROOT%venv\Scripts\pythonw.exe" (
    start "" "%ROOT%venv\Scripts\pythonw.exe" "%ROOT%gui\launcher.pyw" %*
    exit /b 0
)
where pythonw >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Run setup_venv.bat first.
    pause
    exit /b 1
)
start "" pythonw "%ROOT%gui\launcher.pyw" %*
