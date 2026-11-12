# GetOrganelle — macOS Apple Silicon

This package contains a native arm64 build of GetOrganelle 1.8.0.1, SPAdes
4.3.0, Bowtie2 2.5.5, fastp 1.0.1, samtools 1.25, NCBI BLAST+ 2.17.0, and
the GetOrganelle Workbench GUI.

## Requirements

- macOS 15 or newer on Apple Silicon
- Python 3.10+ (python.org, Homebrew, or Xcode Command Line Tools)
- Perl (included with macOS)

## Setup

```bash
./setup_venv.sh
./run_get_organelle_config.sh -a embplant_pt,embplant_mt
```

## Run

```bash
./run_get_organelle_reads.sh -1 R1.fq -2 R2.fq -F embplant_pt -o out -R 15 -k 21,45,65,85,105 -t 8
./run_get_organelle_assembly.sh -a assembly.fasta -F embplant_pt -o out -t 8
./GetOrganelleGUI.sh
```

The launchers put the bundled SPAdes, Bowtie2, and BLAST+ directories on
`PATH`; GetOrganelle itself also looks in
`GetOrganelle/GetOrganelleDep/macOS/`.

## Notes

- The package is built on GitHub's `macos-15` arm64 runner. SPAdes requires
  OpenMP; the build uses Homebrew `libomp`, and the required `libomp.dylib`
  is bundled next to the SPAdes executables.
- The GUI uses PyQt5 (GPLv3/commercial). The command-line toolkit does not
  require Qt.
- BLAST+ is the official NCBI macOS arm64 build.
- See `SOURCE_MANIFEST.md` for component versions and source locations.
