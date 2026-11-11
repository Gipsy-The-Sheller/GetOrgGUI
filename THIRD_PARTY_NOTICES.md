# Third-party notices

This repository contains source snapshots and build recipes for the
following projects.  Each component remains under its own license; the
corresponding license files are kept inside the vendored trees and in the
generated release packages.

| Component | Version | License | Location |
| --- | --- | --- | --- |
| GetOrganelle | 1.8.0.1 | GPLv3 | `GetOrganelle/LICENSE` |
| SPAdes | 4.3.0 | GPLv2 | `vendor/spades/GPLv2.txt`, `vendor/spades/LICENSE` |
| Bowtie2 | 2.5.5 | GPLv3 | `vendor/bowtie2/LICENSE` |
| fastp | 1.0.1 | MIT | `vendor/fastp/LICENSE` |
| samtools / htslib | 1.25 | MIT / Expat | `vendor/samtools/LICENSE`, `vendor/samtools/htslib-1.25/LICENSE` |
| NCBI BLAST+ | 2.17.0 | NCBI public domain notice | downloaded at build time; `LICENSE` is shipped in the package |
| zlib-ng, Blaze, HMMER/easel, BamTools, BWA, LLVM, Boost | bundled with SPAdes | see `vendor/spades/ext` | `vendor/spades/ext/...` |

The Windows porting patches for SPAdes are distributed under GPLv2, the
same license as SPAdes.  The GetOrganelle patches are distributed under
GPLv3, the same license as GetOrganelle.
