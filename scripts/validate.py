#!/usr/bin/env python3
"""Validate the fixed f2x50 repository and probe manifests."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

EXPECTED_REPOSITORIES = {"low": 20, "medium": 20, "complex": 10}
EXPECTED_VERSION = "1.0.0"
EXPECTED_PROBES = {"low": 203, "medium": 201, "complex": 157}
EXPECTED_MODES = {
    "numeric": 280,
    "exact-array": 158,
    "exact": 80,
    "exact-bool-array": 33,
    "exact-bool": 5,
    "exact-duration-seconds": 5,
}
EXPECTED_ORACLE_KINDS = {
    "original-file-plus-driver": 446,
    "extracted-source": 8,
    "inline-reimplementation": 73,
    "synthetic-fixture": 34,
}
EXPECTED_DIRECT_SOURCE_REPOSITORIES = 50
EXPECTED_DIRECT_SOURCE_PAIRS = 131
EXPECTED_MULTI_SYMBOL_REPOSITORIES = 50
REPOSITORY_FIELDS = {
    "benchmark_id",
    "tier",
    "repository",
    "directory",
    "upstream_url",
    "revision",
    "revision_date",
    "fortran_files",
    "fortran_loc",
    "domain",
    "license_spdx",
    "license_status",
    "license_evidence",
}
PROBE_FIELDS = {
    "probe_id",
    "tier",
    "repository",
    "case_name",
    "comparison_mode",
    "source_oracle",
    "definition_file",
}
SOURCE_INFORMATION_FIELDS = {
    "probe_id",
    "oracle_kind",
    "upstream_path",
    "upstream_symbol",
    "upstream_start_line",
    "upstream_end_line",
    "harness_path",
    "harness_start_line",
    "harness_end_line",
    "source_note",
}
ORACLE_KINDS = {
    "original-file-plus-driver",
    "extracted-source",
    "f2py-wrapper",
    "inline-reimplementation",
    "synthetic-fixture",
}


def read_csv(path: Path, required: set[str], errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing = required - fields
            if missing:
                errors.append(f"{path}: missing columns {sorted(missing)}")
            return list(reader)
    except FileNotFoundError:
        errors.append(f"{path}: file not found")
        return []


def duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        release_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        release_version = ""
        errors.append(f"{root / 'VERSION'}: file not found")
    if release_version and release_version != EXPECTED_VERSION:
        errors.append(f"release version {release_version!r} != {EXPECTED_VERSION!r}")

    try:
        citation_text = (root / "CITATION.cff").read_text(encoding="utf-8")
    except FileNotFoundError:
        citation_text = ""
        errors.append(f"{root / 'CITATION.cff'}: file not found")
    citation_match = re.search(r"^version:\s*[\"']?([^\"'\s]+)", citation_text, re.MULTILINE)
    citation_version = citation_match.group(1) if citation_match else ""
    if citation_text and not citation_match:
        errors.append(f"{root / 'CITATION.cff'}: version field not found")
    elif citation_version != release_version:
        errors.append(
            f"CITATION.cff version {citation_version!r} != VERSION {release_version!r}"
        )

    repositories = read_csv(root / "manifests/repositories.csv", REPOSITORY_FIELDS, errors)
    probes = read_csv(root / "manifests/probes.csv", PROBE_FIELDS, errors)
    source_information = read_csv(
        root / "manifests/source_information.csv", SOURCE_INFORMATION_FIELDS, errors
    )

    repo_counts = Counter(row.get("tier", "") for row in repositories)
    if repo_counts != Counter(EXPECTED_REPOSITORIES):
        errors.append(f"repository tier counts {dict(repo_counts)} != {EXPECTED_REPOSITORIES}")
    probe_counts = Counter(row.get("tier", "") for row in probes)
    if probe_counts != Counter(EXPECTED_PROBES):
        errors.append(f"probe tier counts {dict(probe_counts)} != {EXPECTED_PROBES}")
    mode_counts = Counter(row.get("comparison_mode", "") for row in probes)
    if mode_counts != Counter(EXPECTED_MODES):
        errors.append(f"comparison-mode counts {dict(mode_counts)} != {EXPECTED_MODES}")
    oracle_counts = Counter(row.get("oracle_kind", "") for row in source_information)
    if oracle_counts != Counter(EXPECTED_ORACLE_KINDS):
        errors.append(f"oracle-kind counts {dict(oracle_counts)} != {EXPECTED_ORACLE_KINDS}")

    repository_by_probe = {row.get("probe_id", ""): row.get("repository", "") for row in probes}
    direct_by_repository = Counter(
        repository_by_probe.get(row.get("probe_id", ""), "")
        for row in source_information
        if row.get("oracle_kind") == "original-file-plus-driver"
    )
    direct_by_repository.pop("", None)
    if len(direct_by_repository) != EXPECTED_DIRECT_SOURCE_REPOSITORIES:
        errors.append(
            f"direct-source repository coverage {len(direct_by_repository)} != "
            f"{EXPECTED_DIRECT_SOURCE_REPOSITORIES}"
        )
    undercovered = sorted(name for name, count in direct_by_repository.items() if count < 5)
    if undercovered:
        errors.append(f"repositories with fewer than five direct-source probes: {undercovered}")

    direct_symbols_by_repository: dict[str, set[tuple[str, str]]] = {}
    for row in source_information:
        if row.get("oracle_kind") != "original-file-plus-driver":
            continue
        repository = repository_by_probe.get(row.get("probe_id", ""), "")
        direct_symbols_by_repository.setdefault(repository, set()).add(
            (row.get("upstream_path", ""), row.get("upstream_symbol", ""))
        )
    direct_pair_count = sum(len(symbols) for symbols in direct_symbols_by_repository.values())
    if direct_pair_count != EXPECTED_DIRECT_SOURCE_PAIRS:
        errors.append(
            f"direct-source repository-symbol pairs {direct_pair_count} != "
            f"{EXPECTED_DIRECT_SOURCE_PAIRS}"
        )
    multi_symbol_count = sum(
        len(symbols) >= 2 for symbols in direct_symbols_by_repository.values()
    )
    if multi_symbol_count != EXPECTED_MULTI_SYMBOL_REPOSITORIES:
        errors.append(
            f"repositories with at least two direct-source symbols {multi_symbol_count} != "
            f"{EXPECTED_MULTI_SYMBOL_REPOSITORIES}"
        )

    for label, values in (
        ("benchmark_id", [row.get("benchmark_id", "") for row in repositories]),
        ("repository", [row.get("repository", "") for row in repositories]),
        ("directory", [row.get("directory", "") for row in repositories]),
        ("probe_id", [row.get("probe_id", "") for row in probes]),
        ("source-information probe_id", [row.get("probe_id", "") for row in source_information]),
    ):
        repeated = duplicates(values)
        if repeated:
            errors.append(f"duplicate {label} values: {repeated}")

    repo_by_name = {row.get("repository", ""): row for row in repositories}
    probes_per_repo = Counter(row.get("repository", "") for row in probes)
    for row in repositories:
        name = row.get("repository", "")
        if not re.fullmatch(r"[0-9a-f]{40}", row.get("revision", "")):
            errors.append(f"{name}: revision is not a full 40-character Git SHA")
        if not row.get("upstream_url", "").startswith("https://"):
            errors.append(f"{name}: upstream URL must use HTTPS")
        for field in ("fortran_files", "fortran_loc"):
            try:
                if int(row.get(field, "")) <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{name}: {field} must be a positive integer")
        if probes_per_repo[name] < 4:
            errors.append(f"{name}: expected at least four behavioral probes")
        if row.get("license_status") == "no-explicit-license-at-pin" and row.get("license_spdx") != "NOASSERTION":
            errors.append(f"{name}: unlicensed repository must use NOASSERTION")
        if row.get("license_status") == "mixed-or-ambiguous" and row.get("license_spdx") != "NOASSERTION":
            errors.append(f"{name}: ambiguous repository must use NOASSERTION")

    for row in probes:
        repository = row.get("repository", "")
        if repository not in repo_by_name:
            errors.append(f"{row.get('probe_id')}: unknown repository {repository}")
            continue
        if row.get("tier") != repo_by_name[repository].get("tier"):
            errors.append(f"{row.get('probe_id')}: tier disagrees with repository manifest")
        if row.get("source_oracle") != "versioned-source-contract":
            errors.append(f"{row.get('probe_id')}: invalid source_oracle classification")
        definition = root / row.get("definition_file", "")
        if not definition.is_file():
            errors.append(f"{row.get('probe_id')}: missing definition file {definition}")

    probe_ids = {row.get("probe_id", "") for row in probes}
    source_information_ids = {row.get("probe_id", "") for row in source_information}
    if source_information_ids != probe_ids:
        missing = sorted(probe_ids - source_information_ids)
        extra = sorted(source_information_ids - probe_ids)
        errors.append(f"source-information join mismatch: missing={missing}, extra={extra}")
    for row in source_information:
        probe_id = row.get("probe_id", "")
        kind = row.get("oracle_kind", "")
        if kind not in ORACLE_KINDS:
            errors.append(f"{probe_id}: invalid oracle_kind {kind!r}")
        if not row.get("source_note", "").strip():
            errors.append(f"{probe_id}: missing provenance note")
        for start_name, end_name in (
            ("harness_start_line", "harness_end_line"),
            ("upstream_start_line", "upstream_end_line"),
        ):
            start = row.get(start_name, "")
            end = row.get(end_name, "")
            if bool(start) != bool(end):
                errors.append(f"{probe_id}: incomplete {start_name}/{end_name} range")
            elif start and (not start.isdigit() or not end.isdigit() or int(start) > int(end)):
                errors.append(f"{probe_id}: invalid {start_name}/{end_name} range")
        harness_path = root / row.get("harness_path", "")
        if not harness_path.is_file():
            errors.append(f"{probe_id}: missing source-information harness file {harness_path}")
        has_locator = bool(row.get("upstream_path"))
        if has_locator != bool(row.get("upstream_symbol")):
            errors.append(f"{probe_id}: incomplete upstream path/symbol locator")
        if kind in {"original-file-plus-driver", "extracted-source", "f2py-wrapper"} and not has_locator:
            errors.append(f"{probe_id}: {kind} requires an upstream locator")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        print("f2x50 validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"f2x50 validation passed: {sum(EXPECTED_REPOSITORIES.values())} repositories and {sum(EXPECTED_PROBES.values())} behavioral probes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
