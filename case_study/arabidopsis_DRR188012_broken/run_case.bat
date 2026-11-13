@echo off
setlocal
set "PYTHONPATH=E:\Codes\getorg_win\gui"
set "PYTHONUTF8=1"
"E:\Codes\getorg_win\venv\Scripts\python.exe" -m getorganelle_gui.cli run ^
  --getorganelle-root "E:\Codes\getorg_win\GetOrganelle" ^
  --dep-root "E:\Codes\getorg_win\GetOrganelle\GetOrganelleDep\Windows" ^
  --python "E:\Codes\getorg_win\venv\Scripts\python.exe" ^
  --config-dir "C:\Users\ASUS\.GetOrganelle" ^
  --workspace "C:\Users\ASUS\arabidopsis_case\runs" ^
  --mode reads ^
  --reads1 "C:\Users\ASUS\arabidopsis_case\fastq_plain\DRR188012_1.fastq" ^
  --reads2 "C:\Users\ASUS\arabidopsis_case\fastq_plain\DRR188012_2.fastq" ^
  --organelle embplant_pt ^
  --run-name arabidopsis_5gb ^
  --threads 12 ^
  --preprocess --fastp-gbase 5.0 --json
