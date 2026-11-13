#!/usr/bin/env python3
"""Two-panel Figure 1 for the Col-0 case study.

Panel A: assembly versus NC_000932.1.
Panel B: assembly self-comparison.

Forward-strand HSPs are drawn in #ba3e45, reverse-complement HSPs in #4e699a.
Identity is not encoded; the previous colourbar/legend is intentionally absent.
The assembly label is placed vertically as the y-axis label of panel A.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

HERE = Path(__file__).resolve().parent

C_FWD = "#ba3e45"
C_REV = "#4e699a"
INK = "#1a1a1a"
MUTED = "#4d4d4d"
GRID = "#dcdcdc"
SURFACE = "#ffffff"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Segoe UI", "DejaVu Sans"],
    "font.size": 9.0,
    "axes.edgecolor": MUTED,
    "axes.linewidth": 0.8,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 8.0,
    "ytick.labelsize": 8.0,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def read_hits(path: Path, min_length: int = 200) -> list[dict]:
    hits = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 15:
            continue
        try:
            hit = {
                "qseqid": fields[0],
                "pident": float(fields[2]),
                "length": int(fields[3]),
                "qstart": int(fields[6]),
                "qend": int(fields[7]),
                "sstart": int(fields[8]),
                "send": int(fields[9]),
                "strand": fields[12],
            }
        except ValueError:
            continue
        if hit["length"] < min_length:
            continue
        hits.append(hit)
    return hits


def by_strand(hits: list[dict]) -> tuple[list, list]:
    forward, reverse = [], []
    for hit in hits:
        segment = [(hit["sstart"], hit["qstart"]), (hit["send"], hit["qend"])]
        (forward if hit["strand"] == "plus" else reverse).append(segment)
    return forward, reverse


def draw_panel(ax, hits, xlim, ylim, xlabel, ylabel, letter):
    forward, reverse = by_strand(hits)
    ax.add_collection(LineCollection(forward, colors=C_FWD, linewidths=1.25,
                                     capstyle="butt", zorder=2))
    ax.add_collection(LineCollection(reverse, colors=C_REV, linewidths=1.25,
                                     capstyle="butt", zorder=3))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(xlabel, labelpad=4)
    ax.set_ylabel(ylabel, labelpad=6)
    ticks = [0, 50_000, 100_000, 150_000]
    labels = ["0", "50k", "100k", "150k"]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.8)
    ax.set_title(letter, loc="left", fontsize=12, fontweight="bold",
                 family="serif", color=INK, pad=5)


def main() -> None:
    hits_ref = read_hits(HERE / "hits_strand.tsv")
    hits_self = read_hits(HERE / "self_hits.tsv")

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(7.4, 3.9), constrained_layout=True
    )

    draw_panel(
        ax_a,
        hits_ref,
        xlim=(0, 154_478),
        ylim=(0, 154_479),
        xlabel="NC_000932.1 position (bp)",
        ylabel="Col-0_cpDNA_circular_154479bp (154,479 bp)",
        letter="A",
    )
    draw_panel(
        ax_b,
        hits_self,
        xlim=(0, 154_479),
        ylim=(0, 154_479),
        xlabel="Assembly position (bp)",
        ylabel="Assembly position (bp)",
        letter="B",
    )


    fig.savefig(HERE / "figure1.pdf", dpi=300)
    fig.savefig(HERE / "figure1.png", dpi=300)
    print("wrote figure1.pdf and figure1.png")
    print(f"panel A: {len(hits_ref)} HSPs; panel B: {len(hits_self)} HSPs")


if __name__ == "__main__":
    main()
