#!/usr/bin/env python3
"""Print a compact Markdown summary of the f2x50 manifests."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "manifests/repositories.csv").open(newline="", encoding="utf-8") as handle:
        repositories = list(csv.DictReader(handle))
    with (root / "manifests/probes.csv").open(newline="", encoding="utf-8") as handle:
        probes = list(csv.DictReader(handle))

    by_tier: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in repositories:
        by_tier[row["tier"]].append(row)
    probe_counts = Counter(row["tier"] for row in probes)

    print("| Tier | Repositories | Fortran files | Physical lines | Probes |")
    print("|---|---:|---:|---:|---:|")
    for tier in ("low", "medium", "complex"):
        rows = by_tier[tier]
        print(
            f"| {tier.capitalize()} | {len(rows)} | "
            f"{sum(int(row['fortran_files']) for row in rows):,} | "
            f"{sum(int(row['fortran_loc']) for row in rows):,} | {probe_counts[tier]} |"
        )
    print(
        f"| **Total** | **{len(repositories)}** | "
        f"**{sum(int(row['fortran_files']) for row in repositories):,}** | "
        f"**{sum(int(row['fortran_loc']) for row in repositories):,}** | **{len(probes)}** |"
    )


if __name__ == "__main__":
    main()
