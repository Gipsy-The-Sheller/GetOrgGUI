#!/usr/bin/env python3
"""Draw a BLAST dot plot of assembled scaffolds against a reference.

Usage:
    python dotplot.py hits.tsv assembly.fasta reference.fasta out.pdf

The BLAST table is the standard 12-column outfmt 6:
qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore

Scaffolds are stacked in FASTA order; each hit is drawn as a segment whose
colour encodes percent identity.  Hits are filtered by identity and alignment
length, and the fraction of the reference covered by retained hits is printed.
"""
from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection


def read_fasta_lengths(path: Path) -> "OrderedDict[str, int]":
    lengths: "OrderedDict[str, int]" = OrderedDict()
    name = ""
    length = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name:
                    lengths[name] = length
                name = line[1:].split()[0]
                length = 0
            elif name:
                length += len(line)
    if name:
        lengths[name] = length
    return lengths


def read_hits(path: Path) -> List[Tuple[str, str, float, int, int, int, int, int]]:
    hits = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 12:
                continue
            try:
                hits.append(
                    (
                        fields[0],
                        fields[1],
                        float(fields[2]),
                        int(fields[3]),
                        int(fields[6]),
                        int(fields[7]),
                        int(fields[8]),
                        int(fields[9]),
                    )
                )
            except ValueError:
                continue
    return hits


def union_length(intervals: List[Tuple[int, int]]) -> int:
    if not intervals:
        return 0
    intervals.sort()
    total = 0
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blast_table", type=Path)
    parser.add_argument("assembly_fasta", type=Path)
    parser.add_argument("reference_fasta", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--min-identity", type=float, default=90.0)
    parser.add_argument("--min-length", type=int, default=200)
    parser.add_argument("--max-evalue", type=float, default=1e-5)
    parser.add_argument("--title", default="Assembly versus chloroplast reference")
    args = parser.parse_args()

    query_lengths = read_fasta_lengths(args.assembly_fasta)
    reference_lengths = read_fasta_lengths(args.reference_fasta)
    if not query_lengths or not reference_lengths:
        print("Empty FASTA input", file=sys.stderr)
        return 2
    reference_name, reference_length = next(iter(reference_lengths.items()))

    hits = []
    for qname, sname, pident, length, qstart, qend, sstart, send in read_hits(args.blast_table):
        if qname not in query_lengths:
            continue
        if pident < args.min_identity or length < args.min_length:
            continue
        hits.append((qname, pident, length, qstart, qend, sstart, send))
    if not hits:
        print("No hits passed the filters", file=sys.stderr)
        return 1

    # Keep scaffolds with hits, in FASTA order, and give each a stacked y offset.
    hit_counts: Dict[str, int] = {}
    hit_bases: Dict[str, int] = {}
    for qname, pident, length, qstart, qend, sstart, send in hits:
        hit_counts[qname] = hit_counts.get(qname, 0) + 1
        hit_bases[qname] = hit_bases.get(qname, 0) + length
    contigs = [name for name in query_lengths if hit_counts.get(name)]
    contigs.sort(key=lambda name: (-hit_bases.get(name, 0), query_lengths[name] * -1))
    offsets: Dict[str, int] = {}
    cursor = 0
    for name in contigs:
        offsets[name] = cursor
        cursor += query_lengths[name]
    total_query = max(cursor, 1)

    segments = []
    colors = []
    subject_intervals: List[Tuple[int, int]] = []
    for qname, pident, length, qstart, qend, sstart, send in hits:
        y1, y2 = sorted((qstart, qend))
        x1, x2 = sorted((sstart, send))
        segments.append(
            [
                (x1, offsets[qname] + y1),
                (x2, offsets[qname] + y2),
            ]
        )
        colors.append(pident)
        subject_intervals.append((x1, x2))

    fig, ax = plt.subplots(figsize=(8.0, 6.0), constrained_layout=True)
    collection = LineCollection(segments, cmap="viridis", linewidths=1.2, alpha=0.8)
    collection.set_array(np.asarray(colors))
    collection.set_clim(args.min_identity, 100.0)
    ax.add_collection(collection)

    for name in contigs:
        y = offsets[name]
        ax.axhline(y, color="#cccccc", linewidth=0.4, zorder=0)
        ax.text(
            reference_length * 1.01,
            y + query_lengths[name] / 2,
            f"{name}  ({query_lengths[name]:,} bp)",
            va="center",
            ha="left",
            fontsize=7,
            clip_on=False,
        )

    ax.set_xlim(0, reference_length)
    ax.set_ylim(0, total_query)
    tick_step = 50000
    ticks = list(range(0, reference_length + 1, tick_step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{value // 1000}k" if value else "0" for value in ticks])
    ax.tick_params(axis="both", labelsize=9)
    ax.set_xlabel(f"{reference_name} position (bp)")
    ax.set_ylabel("Assembled scaffolds (stacked, bp)")
    ax.set_title(args.title)
    ax.grid(False)
    cbar = fig.colorbar(collection, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("BLAST identity (%)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300)
    if args.output.suffix.lower() == ".pdf":
        fig.savefig(args.output.with_suffix(".png"), dpi=300)
    print(f"wrote {args.output}")

    covered = union_length(subject_intervals)
    print(f"reference length: {reference_length:,} bp")
    print(f"reference covered by retained hits: {covered:,} bp ({covered / reference_length * 100:.1f}%)")
    print(f"retained hits: {len(hits)}; query scaffolds: {len(contigs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
