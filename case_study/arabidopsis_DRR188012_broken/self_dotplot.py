#!/usr/bin/env python3
"""Draw an all-vs-all self dot plot from a BLAST table.

Usage:
    python self_dotplot.py self_hits.tsv assembly.fasta out.pdf

The BLAST table must be outfmt 6 with the extra fields:

    qseqid sseqid pident length mismatch gapopen qstart qend sstart send \
    evalue bitscore sstrand qlen slen

Scaffolds are laid out head-to-tail on both axes in FASTA order.  Direct
(plus-strand) hits follow the main diagonal; reverse-complement hits form
anti-diagonal segments.  The plastid inverted repeat therefore appears as
off-diagonal anti-diagonal blocks.
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
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D


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


def read_hits(path: Path) -> List[Tuple[str, str, float, int, int, int, int, str]]:
    hits = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 13:
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
                        fields[12],
                    )
                )
            except ValueError:
                continue
    return hits


def short_name(name: str) -> str:
    return name.split("--")[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blast_table", type=Path)
    parser.add_argument("assembly_fasta", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--min-identity", type=float, default=95.0)
    parser.add_argument("--min-length", type=int, default=500)
    parser.add_argument("--max-evalue", type=float, default=1e-5)
    parser.add_argument("--title", default="Assembly self-comparison")
    args = parser.parse_args()

    lengths = read_fasta_lengths(args.assembly_fasta)
    if not lengths:
        print("Empty FASTA input", file=sys.stderr)
        return 2

    offsets: Dict[str, int] = {}
    cursor = 0
    for name, length in lengths.items():
        offsets[name] = cursor
        cursor += length
    total = cursor

    hits = []
    for qname, sname, pident, aln_len, qs, qe, ss, se, strand in read_hits(args.blast_table):
        if qname not in offsets or sname not in offsets:
            continue
        if pident < args.min_identity or aln_len < args.min_length:
            continue
        hits.append((qname, sname, pident, aln_len, qs, qe, ss, se, strand))
    if not hits:
        print("No hits passed the filters", file=sys.stderr)
        return 1

    diagonal: List[List[Tuple[float, float]]] = []
    plus: List[List[Tuple[float, float]]] = []
    minus: List[List[Tuple[float, float]]] = []
    minus_blocks = []
    for qname, sname, pident, aln_len, qs, qe, ss, se, strand in hits:
        q_off = offsets[qname]
        s_off = offsets[sname]
        segment = [
            (ss + s_off, qs + q_off),
            (se + s_off, qe + q_off),
        ]
        # A full-contig plus-strand hit is the trivial self diagonal.
        if (
            qname == sname
            and strand == "plus"
            and qs == 1
            and qe == lengths[qname]
            and ss == 1
            and se == lengths[sname]
        ):
            diagonal.append(segment)
        elif strand == "minus":
            minus.append(segment)
            minus_blocks.append((qname, sname, aln_len, qs, qe, ss, se))
        else:
            plus.append(segment)

    fig, ax = plt.subplots(figsize=(7.6, 7.6), constrained_layout=True)
    if diagonal:
        ax.add_collection(
            LineCollection(diagonal, colors="#bdbdbd", linewidths=1.0, zorder=1)
        )
    if plus:
        ax.add_collection(
            LineCollection(plus, colors="#2c7fb8", linewidths=1.4, alpha=0.9, zorder=2)
        )
    ax.add_collection(
        LineCollection(minus, colors="#c0392b", linewidths=1.8, alpha=0.9, zorder=3)
    )

    # Contig boundaries and labels.
    for name, length in lengths.items():
        start = offsets[name]
        ax.axvline(start, color="#eeeeee", linewidth=0.6, zorder=0)
        ax.axhline(start, color="#eeeeee", linewidth=0.6, zorder=0)
        mid = start + length / 2
        label = f"{short_name(name)}\n({length:,} bp)"
        ax.text(
            mid,
            -total * 0.012,
            label,
            ha="center",
            va="top",
            fontsize=7,
            clip_on=False,
        )
        ax.text(
            -total * 0.012,
            mid,
            short_name(name),
            ha="right",
            va="center",
            fontsize=7,
            rotation=90,
            clip_on=False,
        )

    # Annotate the two IR blocks once each; reciprocal HSPs are the same block.
    seen = set()
    for qname, sname, aln_len, qs, qe, ss, se in minus_blocks:
        key = (frozenset((qname, sname)), aln_len)
        if key in seen:
            continue
        seen.add(key)
        x = (ss + se) / 2 + offsets[sname]
        y = (qs + qe) / 2 + offsets[qname]
        ax.annotate(
            f"IR RC\n{aln_len:,} bp",
            xy=(x, y),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=7,
            color="#c0392b",
            arrowprops=dict(arrowstyle="-", color="#c0392b", linewidth=0.6),
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8),
        )

    ax.set_xlim(0, total)
    ax.set_ylim(0, total)
    ax.set_aspect("equal")
    ticks = [0] + [offsets[name] for name in lengths] + [total]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([f"{value:,}" for value in ticks], fontsize=7)
    ax.set_yticklabels([f"{value:,}" for value in ticks], fontsize=7)
    ax.set_xlabel("Assembly coordinate (bp)")
    ax.set_ylabel("Assembly coordinate (bp)")
    ax.set_title(args.title)
    ax.grid(False)

    legend_handles = [
        Line2D([0], [0], color="#bdbdbd", linewidth=1.0, label="self diagonal"),
        Line2D([0], [0], color="#c0392b", linewidth=1.8, label="reverse complement"),
        Line2D([0], [0], color="#2c7fb8", linewidth=1.4, label="direct repeat"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper right",
        fontsize=7,
        frameon=True,
        framealpha=0.9,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300)
    if args.output.suffix.lower() == ".pdf":
        fig.savefig(args.output.with_suffix(".png"), dpi=300)
    print(f"wrote {args.output}")

    print(f"assembly length: {total:,} bp")
    print(f"retained hits: {len(hits)}; RC hits: {len(minus)}; plus hits: {len(plus)}")
    for qname, sname, aln_len, qs, qe, ss, se in sorted(
        set(minus_blocks), key=lambda row: -row[2]
    ):
        print(
            f"  RC {aln_len:,} bp: {short_name(qname)} {qs:,}-{qe:,} "
            f"<-> {short_name(sname)} {ss:,}-{se:,}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
