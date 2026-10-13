#!/usr/bin/env python3
"""Build a target-independent probe catalogue from an evaluation result table.

The input table may contain target-specific outcomes. This script deliberately
emits only benchmark design metadata; pass/fail states and error magnitudes are
not part of the f2x50 dataset definition.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

FIELDS = (
    "probe_id",
    "tier",
    "repository",
    "case_name",
    "comparison_mode",
    "source_oracle",
    "definition_file",
)

MAIN_HARNESS_REPOSITORIES = {
    "tsunami",
    "FKB",
    "fastGPT",
    "datetime-fortran",
    "M_strings",
    "fftpack",
    "fortranlib",
    "fortran-utils",
    "minpack",
    "SISSO",
    "json-fortran",
    "Fortran-Astrodynamics-Toolkit",
    "quadpack",
    "wavelets",
    "lapack",
    "pymc2",
    "Nek5000",
    "fpm",
    "ccpp-physics",
    "petsc",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build(input_path: Path, output_path: Path) -> None:
    counters: defaultdict[tuple[str, str], int] = defaultdict(int)
    output_rows: list[dict[str, str]] = []
    with input_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            tier = row["tier"]
            repository = row["repository"]
            counters[(tier, repository)] += 1
            sequence = counters[(tier, repository)]
            definition = (
                "harness/python/run_corpus_verification.py"
                if repository in MAIN_HARNESS_REPOSITORIES
                else "harness/python/extended_repo_verifiers.py"
            )
            output_rows.append(
                {
                    "probe_id": f"f2x50-{tier}-{slug(repository)}-{sequence:03d}",
                    "tier": tier,
                    "repository": repository,
                    "case_name": row["routine"],
                    "comparison_mode": row["comparison"],
                    "source_oracle": "versioned-source-contract",
                    "definition_file": definition,
                }
            )

    output_rows.sort(key=lambda item: (item["tier"], item["repository"].casefold(), item["probe_id"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="routine-level evaluation CSV")
    parser.add_argument("output", type=Path, help="target-independent probe manifest")
    args = parser.parse_args()
    build(args.input, args.output)


if __name__ == "__main__":
    main()
