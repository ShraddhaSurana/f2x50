#!/usr/bin/env python3
"""Summarize probe density, oracle strength, and a deterministic audit sample."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


ORACLE_ORDER = (
    "original-file-plus-driver",
    "f2py-wrapper",
    "extracted-source",
    "inline-reimplementation",
    "synthetic-fixture",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    repositories = read_csv(root / "manifests/repositories.csv")
    probes = read_csv(root / "manifests/probes.csv")
    source_information = read_csv(root / "manifests/source_information.csv")
    source_information_by_id = {row["probe_id"]: row for row in source_information}
    probes_by_repo: dict[str, list[dict[str, str]]] = defaultdict(list)
    for probe in probes:
        probes_by_repo[probe["repository"]].append(probe)

    coverage_rows: list[dict[str, object]] = []
    sample_rows: list[dict[str, object]] = []
    for repository in repositories:
        name = repository["repository"]
        repo_probes = probes_by_repo[name]
        kind_counts = Counter(source_information_by_id[row["probe_id"]]["oracle_kind"] for row in repo_probes)
        loc = int(repository["fortran_loc"])
        located_symbols = {
            (
                source_information_by_id[row["probe_id"]]["upstream_path"],
                source_information_by_id[row["probe_id"]]["upstream_symbol"],
            )
            for row in repo_probes
            if source_information_by_id[row["probe_id"]]["upstream_symbol"]
        }
        coverage_rows.append(
            {
                "benchmark_id": repository["benchmark_id"],
                "tier": repository["tier"],
                "repository": name,
                "fortran_loc": loc,
                "probe_count": len(repo_probes),
                "probes_per_kloc": f"{1000.0 * len(repo_probes) / loc:.6f}",
                "located_upstream_symbols": len(located_symbols),
                **{kind: kind_counts[kind] for kind in ORACLE_ORDER},
            }
        )
        chosen = min(
            repo_probes,
            key=lambda row: hashlib.sha256(
                f"f2x50-v0.1-independent-audit:{row['probe_id']}".encode()
            ).hexdigest(),
        )
        source = source_information_by_id[chosen["probe_id"]]
        sample_rows.append(
            {
                "benchmark_id": repository["benchmark_id"],
                "tier": repository["tier"],
                "repository": name,
                "probe_id": chosen["probe_id"],
                "case_name": chosen["case_name"],
                "oracle_kind": source["oracle_kind"],
                "review_status": "pending-independent-review",
                "reviewer": "",
                "review_notes": "",
            }
        )

    coverage_fields = [
        "benchmark_id",
        "tier",
        "repository",
        "fortran_loc",
        "probe_count",
        "probes_per_kloc",
        "located_upstream_symbols",
        *ORACLE_ORDER,
    ]
    write_csv(root / "manifests/coverage_by_repository.csv", coverage_rows, coverage_fields)
    write_csv(
        root / "manifests/independent_audit_sample.csv",
        sample_rows,
        list(sample_rows[0]),
    )

    total_loc = sum(int(row["fortran_loc"]) for row in repositories)
    total_kinds = Counter(row["oracle_kind"] for row in source_information)
    densities = [float(row["probes_per_kloc"]) for row in coverage_rows]
    lines = [
        "# Behavioral-coverage audit",
        "",
        "This report quantifies the released behavioral contract; it does not claim statement, branch, or semantic coverage of the upstream repositories.",
        "",
        "## Release-level summary",
        "",
        f"- {len(probes)} probes across {len(repositories)} repositories ({len(probes) / len(repositories):.2f} probes per repository).",
        f"- {len(probes) / (total_loc / 1000):.6f} probes per thousand physical Fortran lines corpus-wide.",
        f"- Per-repository density ranges from {min(densities):.6f} to {max(densities):.6f} probes per KLOC; size therefore makes raw line-normalized density highly uneven.",
        "",
        "| Source evidence | Probes | Share |",
        "|---|---:|---:|",
    ]
    for kind in ORACLE_ORDER:
        count = total_kinds[kind]
        lines.append(f"| `{kind}` | {count} | {100.0 * count / len(probes):.1f}% |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The fixed contract guarantees breadth across all 50 repositories and preserves every planned case in the denominator. It is targeted regression evidence, not a proof of repository equivalence. Original-file and f2py probes provide the strongest direct source connection. Inline reimplementations and synthetic fixtures are disclosed separately because compiling a small Fortran program is not by itself evidence that the pinned upstream implementation was executed.",
            "",
            "`manifests/coverage_by_repository.csv` supports tier/repository decompositions. `manifests/independent_audit_sample.csv` deterministically selects one probe per repository using SHA-256 over the stable probe ID. A person who did not author the corresponding verifier should check the source locator, input, expected behavior, and comparison rule and fill the three review columns. Until then, the sample is explicitly marked pending and must not be described as independently audited.",
            "",
            "## Recommended expansion rule",
            "",
            "Future versions should prioritize public routines not yet represented, boundary/error cases, and probes that replace inline reimplementations with execution of the pinned source. Additions must be selected without inspecting a migration method's pass/fail outcomes and must increment the benchmark version.",
            "",
        ]
    )
    (root / "docs/coverage-audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote coverage audit, per-repository metrics, and 50-probe review sample")


if __name__ == "__main__":
    main()
