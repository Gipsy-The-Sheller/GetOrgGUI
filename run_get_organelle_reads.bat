@echo off
setlocal
set "ROOT=%~dp0"
set "PATH=%ROOT%venv\Scripts;%ROOT%GetOrganelle\GetOrganelleDep\Windows\bowtie2;%ROOT%GetOrganelle\GetOrganelleDep\Windows\ncbi-blast;%ROOT%GetOrganelle\GetOrganelleDep\Windows\SPAdes\bin;%PATH%"
"%ROOT%venv\Scripts\python.exe" "%ROOT%GetOrganelle\get_organelle_from_reads.py" %*
