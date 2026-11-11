# License and source notice

GetOrganelle Workbench original code — the PyQt5 GUI, CLI, tests, build
scripts, CI configuration and documentation authored for this repository — is
licensed under the **GNU Affero General Public License, version 3 only
(AGPL-3.0-only)**. See [LICENSE](LICENSE).

This license does **not** relicense the vendored third-party sources or the
binaries built from them. They remain under their upstream licenses:

- GetOrganelle: GPLv3
- SPAdes: GPLv2 (bundled `ext` components have their own licenses)
- Bowtie2: GPLv3
- fastp: MIT
- samtools / htslib: MIT/Expat
- NCBI BLAST+: public domain
- PyQt5: GPLv3 or a commercial Qt/PyQt license

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the license files in
the vendored trees for details.

The GUI uses PyQt5 under its GPLv3 option; the AGPLv3 original code and the
GPLv3 PyQt5 library are combined in the distributed GUI. Anyone redistributing
the GUI must comply with both the AGPLv3 and the applicable PyQt5 terms (or use
a commercial PyQt license). The vendored GetOrganelle, SPAdes and Bowtie2
programs are invoked as separate executables; their own licenses continue to
apply.

## Corresponding source and network use

Release packages include this notice and a source manifest. The corresponding
source is available from:

https://github.com/Gipsy-The-Sheller/GetOrgGUI

The source archive for a tagged release contains the exact GetOrganelle,
SPAdes, Bowtie2, fastp and samtools source snapshots and Windows patches used
to build that release, together with the build scripts and CI configuration.

Under AGPLv3 section 13, users interacting with the work over a network must be
offered the Corresponding Source. This repository and the release source
archive provide it.

## PyQt5 alternative

If a permissive license for the GUI layer is required, PyQt5 must be replaced
with a compatible alternative such as PySide6 under the LGPLv3, or a commercial
PyQt license must be obtained. The current release intentionally uses PyQt5
and AGPLv3.
