#!/usr/bin/env python3
"""Regenerate publication-ready descriptive figures from the manifests."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {"low": "#0072B2", "medium": "#E69F00", "complex": "#CC79A7"}
TIERS = ("low", "medium", "complex")


def load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def save(fig: plt.Figure, base: Path) -> None:
    fig.savefig(base.with_suffix(".png"), dpi=240, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def repository_scale(repositories: list[dict[str, str]], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2), constrained_layout=True)
    bins = np.linspace(3.0, 6.3, 12)
    for tier in TIERS:
        rows = [row for row in repositories if row["tier"] == tier]
        loc = np.array([int(row["fortran_loc"]) for row in rows])
        files = np.array([int(row["fortran_files"]) for row in rows])
        axes[0].hist(np.log10(loc), bins=bins, alpha=0.58, label=tier.capitalize(), color=COLORS[tier])
        axes[1].scatter(files, loc, s=42, alpha=0.82, label=tier.capitalize(), color=COLORS[tier], edgecolor="white", linewidth=0.45)
    axes[0].set_xlabel("Repository size (log$_{10}$ physical Fortran lines)")
    axes[0].set_ylabel("Repository count")
    axes[0].set_title("Size distribution")
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Git-tracked Fortran files")
    axes[1].set_ylabel("Physical Fortran lines")
    axes[1].set_title("Files and lines by tier")
    axes[0].legend(frameon=False)
    axes[1].legend(frameon=False)
    fig.suptitle("f2x50 repository scale", fontsize=13)
    save(fig, output / "repository_scale")


def probe_coverage(probes: list[dict[str, str]], output: Path) -> None:
    modes = ["numeric", "exact-array", "exact", "exact-bool-array", "exact-bool", "exact-duration-seconds"]
    labels = ["Numeric", "Exact array", "Exact scalar/string", "Boolean array", "Boolean", "Normalised duration"]
    mode_colors = ["#0072B2", "#56B4E9", "#009E73", "#F0E442", "#E69F00", "#D55E00"]
    fig, ax = plt.subplots(figsize=(8.7, 5.2))
    left = np.zeros(len(TIERS), dtype=int)
    for mode, label, color in zip(modes, labels, mode_colors, strict=True):
        values = np.array([sum(row["tier"] == tier and row["comparison_mode"] == mode for row in probes) for tier in TIERS])
        ax.barh([tier.capitalize() for tier in TIERS], values, left=left, label=label, color=color)
        left += values
    for index, total in enumerate(left):
        ax.text(total + 2, index, str(total), va="center", fontsize=9)
    ax.set_xlim(0, max(left) + 20)
    ax.set_xlabel("Planned behavioral probes")
    ax.set_title(f"f2x50 behavioral-probe coverage (n = {len(probes)})")
    handles, legend_labels = ax.get_legend_handles_labels()
    fig.legend(handles, legend_labels, frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 0.01))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.89, bottom=0.25)
    save(fig, output / "probe_coverage")


def source_information_figure(source_information: list[dict[str, str]], output: Path) -> None:
    order = [
        "original-file-plus-driver",
        "f2py-wrapper",
        "extracted-source",
        "inline-reimplementation",
        "synthetic-fixture",
    ]
    labels = [
        "Original file + driver",
        "f2py wrapper",
        "Text-matched extraction",
        "Inline reimplementation",
        "Synthetic fixture",
    ]
    colors = ["#009E73", "#0072B2", "#56B4E9", "#E69F00", "#CC79A7"]
    counts = Counter(row["oracle_kind"] for row in source_information)
    values = [counts[kind] for kind in order]
    fig, ax = plt.subplots(figsize=(8.7, 4.5))
    bars = ax.barh(labels, values, color=colors)
    ax.bar_label(bars, padding=4)
    ax.set_xlim(0, max(values) * 1.14)
    ax.set_xlabel("Planned probes")
    ax.set_title(f"Source-evidence categories (n = {len(source_information)})")
    fig.text(
        0.95,
        0.04,
        "Categories describe source-side execution, not pass/fail outcomes.",
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#555555",
    )
    fig.subplots_adjust(left=0.28, right=0.95, top=0.87, bottom=0.23)
    save(fig, output / "source_information")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "docs/figures"
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    repositories = load(root / "manifests/repositories.csv")
    probes = load(root / "manifests/probes.csv")
    source_information = load(root / "manifests/source_information.csv")
    repository_scale(repositories, output)
    probe_coverage(probes, output)
    source_information_figure(source_information, output)
    print(f"wrote figures to {output}")


if __name__ == "__main__":
    main()
