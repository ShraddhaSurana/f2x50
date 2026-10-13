from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_FORTRAN_CORPUS_ROOT = Path(
    os.environ.get(
        "F2X_FORTRAN_CORPUS_ROOT",
        str(Path(__file__).resolve().parents[2] / "external" / "fortran_corpus"),
    )
)
DEFAULT_TARGET_ROOT = Path(
    os.environ.get(
        "F2X_TARGET_ROOT",
        str(Path(__file__).resolve().parents[2] / "external" / "targets" / "python"),
    )
)
DEFAULT_REPO_ALIASES = {
    "quadpack-master": "quadpack",
}
FORTRAN_SUFFIXES = {
    ".f",
    ".f03",
    ".f08",
    ".f90",
    ".f95",
    ".for",
    ".ftn",
}
FORTRAN_ROUTINE_RE = re.compile(
    r"^\s*(?!end\b)(?:(?:pure|elemental|recursive|module|impure)\s+)*"
    r"(?:[a-z][a-z0-9_()=*:, \t-]*\s+)?"
    r"(function|subroutine)\s+([a-z][a-z0-9_]*)\b",
    re.IGNORECASE,
)
SYMBOL_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class RoutineCandidate:
    name: str
    fortran_files: tuple[str, ...]
    python_files: tuple[str, ...]


@dataclass(frozen=True)
class RepoInventory:
    tier: str
    fortran_repo_name: str
    python_repo_name: str
    fortran_repo_path: str
    python_repo_path: str
    roundtrip_dfd_path: str | None
    fortran_routine_count: int
    python_routine_count: int
    shared_routine_count: int
    candidate_routines: tuple[RoutineCandidate, ...]


def _iter_fortran_files(repo_root: Path) -> Iterable[Path]:
    for path in repo_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in FORTRAN_SUFFIXES:
            yield path


def extract_fortran_routines(repo_root: Path) -> dict[str, set[str]]:
    routines: dict[str, set[str]] = {}
    for source_path in _iter_fortran_files(repo_root):
        relative_path = str(source_path.relative_to(repo_root))
        try:
            lines = source_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            match = FORTRAN_ROUTINE_RE.match(line)
            if not match:
                continue
            routine_name = match.group(2).lower()
            routines.setdefault(routine_name, set()).add(relative_path)
    return routines


def _symbol_candidates(process_name: str, process_id: str) -> set[str]:
    candidates: set[str] = set()
    stripped_name = process_name.strip().lower()
    if SYMBOL_RE.fullmatch(stripped_name):
        candidates.add(stripped_name)
    stripped_id = process_id.strip().lower()
    if stripped_id:
        tail = stripped_id.split(":")[-1].split(".")[-1].strip()
        if tail and tail != "main" and SYMBOL_RE.fullmatch(tail):
            candidates.add(tail)
    return candidates


def load_python_routines_from_roundtrip(repo_root: Path) -> tuple[dict[str, set[str]], Path | None]:
    comparison_dir = repo_root / "artifacts" / "dfd_comparison"
    roundtrip_path = comparison_dir / "roundtrip_dfd_post_correction.json"
    if not roundtrip_path.exists():
        roundtrip_path = comparison_dir / "roundtrip_dfd.json"
    if not roundtrip_path.exists():
        return {}, None

    try:
        payload = json.loads(roundtrip_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, roundtrip_path

    routines: dict[str, set[str]] = {}
    for process in payload.get("processes", []):
        if not isinstance(process, dict):
            continue
        files = process.get("original_files_associated") or []
        normalized_files = tuple(
            sorted(
                str(item)
                for item in files
                if isinstance(item, str) and item.strip()
            )
        )
        for candidate in _symbol_candidates(
            str(process.get("name") or ""),
            str(process.get("id") or ""),
        ):
            routines.setdefault(candidate, set()).update(normalized_files)
    return routines, roundtrip_path


def build_repo_inventory(
    *,
    tier: str,
    fortran_repo_path: Path,
    python_repo_path: Path,
) -> RepoInventory:
    fortran_routines = extract_fortran_routines(fortran_repo_path)
    python_routines, roundtrip_path = load_python_routines_from_roundtrip(python_repo_path)
    shared_names = sorted(set(fortran_routines) & set(python_routines))
    candidates = tuple(
        RoutineCandidate(
            name=name,
            fortran_files=tuple(sorted(fortran_routines[name])),
            python_files=tuple(sorted(python_routines[name])),
        )
        for name in shared_names
    )
    return RepoInventory(
        tier=tier,
        fortran_repo_name=fortran_repo_path.name,
        python_repo_name=python_repo_path.name,
        fortran_repo_path=str(fortran_repo_path),
        python_repo_path=str(python_repo_path),
        roundtrip_dfd_path=str(roundtrip_path) if roundtrip_path else None,
        fortran_routine_count=len(fortran_routines),
        python_routine_count=len(python_routines),
        shared_routine_count=len(shared_names),
        candidate_routines=candidates,
    )


def inventory_matching_repos(
    *,
    corpus_root: Path = DEFAULT_FORTRAN_CORPUS_ROOT,
    target_root: Path = DEFAULT_TARGET_ROOT,
    repo_aliases: dict[str, str] | None = None,
) -> list[RepoInventory]:
    aliases = dict(DEFAULT_REPO_ALIASES)
    if repo_aliases:
        aliases.update(repo_aliases)

    inventories: list[RepoInventory] = []
    for tier_dir in sorted(path for path in corpus_root.iterdir() if path.is_dir()):
        tier = tier_dir.name
        python_tier_dir = target_root / tier
        if not python_tier_dir.exists():
            continue
        for fortran_repo in sorted(path for path in tier_dir.iterdir() if path.is_dir()):
            python_repo_name = aliases.get(fortran_repo.name, fortran_repo.name)
            python_repo = python_tier_dir / python_repo_name
            if not python_repo.exists():
                continue
            inventories.append(
                build_repo_inventory(
                    tier=tier,
                    fortran_repo_path=fortran_repo,
                    python_repo_path=python_repo,
                )
            )
    return inventories


def select_top_repos(
    inventories: Iterable[RepoInventory],
    *,
    top_per_tier: int = 5,
) -> dict[str, list[RepoInventory]]:
    grouped: dict[str, list[RepoInventory]] = {}
    for inventory in inventories:
        grouped.setdefault(inventory.tier, []).append(inventory)

    selected: dict[str, list[RepoInventory]] = {}
    for tier, items in grouped.items():
        selected[tier] = sorted(
            items,
            key=lambda item: (
                -item.shared_routine_count,
                item.fortran_routine_count,
                item.python_routine_count,
                item.fortran_repo_name.lower(),
            ),
        )[:top_per_tier]
    return selected


def render_selection_markdown(
    selected: dict[str, list[RepoInventory]],
    *,
    max_routines_per_repo: int = 12,
) -> str:
    lines = ["# Corpus Agreement Inventory", ""]
    for tier in ("low", "medium", "complex"):
        repos = selected.get(tier, [])
        lines.append(f"## {tier.capitalize()}")
        lines.append("")
        if not repos:
            lines.append("No matching repos found.")
            lines.append("")
            continue
        lines.append("| Repo | Shared routines | Candidate routines |")
        lines.append("|------|----------------:|--------------------|")
        for repo in repos:
            candidates = ", ".join(
                candidate.name for candidate in repo.candidate_routines[:max_routines_per_repo]
            )
            if len(repo.candidate_routines) > max_routines_per_repo:
                candidates += ", ..."
            lines.append(
                f"| `{repo.fortran_repo_name}` | {repo.shared_routine_count} | {candidates} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def inventories_to_json(inventories: Iterable[RepoInventory]) -> str:
    payload = [asdict(item) for item in inventories]
    return json.dumps(payload, indent=2, sort_keys=True)


def write_inventory_csv(path: Path, inventories: Iterable[RepoInventory]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "tier",
                "fortran_repo_name",
                "python_repo_name",
                "fortran_routine_count",
                "python_routine_count",
                "shared_routine_count",
                "candidate_routines",
                "roundtrip_dfd_path",
            ]
        )
        for item in inventories:
            writer.writerow(
                [
                    item.tier,
                    item.fortran_repo_name,
                    item.python_repo_name,
                    item.fortran_routine_count,
                    item.python_routine_count,
                    item.shared_routine_count,
                    ";".join(candidate.name for candidate in item.candidate_routines),
                    item.roundtrip_dfd_path or "",
                ]
            )
