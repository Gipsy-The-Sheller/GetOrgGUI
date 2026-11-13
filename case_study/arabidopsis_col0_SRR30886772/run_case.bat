@echo off
set PYTHONPATH=E:\Codes\getorg_win\gui
E:\Codes\getorg_win\venv\Scripts\python.exe -m getorganelle_gui.cli run ^
  --getorganelle-root E:\Codes\getorg_win\GetOrganelle ^
  --dep-root E:\Codes\getorg_win\GetOrganelle\GetOrganelleDep\Windows ^
  --python E:\Codes\getorg_win\venv\Scripts\python.exe ^
  --config-dir C:\Users\ASUS\.GetOrganelle ^
  --workspace C:\Users\ASUS\arabidopsis_case\runs ^
  --mode reads ^
  --reads1 C:\Users\ASUS\arabidopsis_case\fastq\SRR30886772_1.fastq.gz ^
  --reads2 C:\Users\ASUS\arabidopsis_case\fastq\SRR30886772_2.fastq.gz ^
  --organelle embplant_pt ^
  --run-name arabidopsis_col0_SRR30886772_5gb ^
  --threads 12 ^
  --preprocess --fastp-gbase 5.0 --json
pause
