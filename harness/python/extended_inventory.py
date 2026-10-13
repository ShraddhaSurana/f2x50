"""Extended routine inventory using generated-Python AST names."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from behavioral_inventory import (
    DEFAULT_TARGET_ROOT,
    DEFAULT_FORTRAN_CORPUS_ROOT,
    DEFAULT_REPO_ALIASES,
    RoutineCandidate,
    build_repo_inventory,
    inventory_matching_repos,
)


@dataclass(frozen=True)
class ExtendedRoutineCandidate:
    name: str
    fortran_files: tuple[str, ...]
    python_files: tuple[str, ...]
    source: str


def extract_python_routines(generated_root: Path) -> dict[str, list[str]]:
    src_root = generated_root / "generated_python" / "src"
    if not src_root.exists():
        return {}
    routines: dict[str, list[str]] = {}
    for path in src_root.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        relative = path.relative_to(src_root).as_posix()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                routines.setdefault(node.name.lower(), []).append(relative)
    return routines


def normalize_python_relative(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    return normalized.removeprefix("src/")


def build_extended_inventory(
    *,
    corpus_root: Path = DEFAULT_FORTRAN_CORPUS_ROOT,
    target_root: Path = DEFAULT_TARGET_ROOT,
) -> list[tuple[object, list[ExtendedRoutineCandidate]]]:
    base = inventory_matching_repos(
        corpus_root=corpus_root,
        target_root=target_root,
        repo_aliases=DEFAULT_REPO_ALIASES,
    )
    extended: list[tuple[object, list[ExtendedRoutineCandidate]]] = []
    for item in base:
        python_routines = extract_python_routines(Path(item.python_repo_path))
        roundtrip_names = {candidate.name for candidate in item.candidate_routines}
        fortran_names = set()
        for candidate in item.candidate_routines:
            fortran_names.add(candidate.name)
        from behavioral_inventory import extract_fortran_routines

        fortran_routines = extract_fortran_routines(Path(item.fortran_repo_path))
        shared = sorted(set(fortran_routines) & set(python_routines))
        candidates: list[ExtendedRoutineCandidate] = []
        seen: set[str] = set()
        for name in shared:
            if name in seen:
                continue
            seen.add(name)
            roundtrip = next(
                (candidate for candidate in item.candidate_routines if candidate.name == name),
                None,
            )
            fortran_files = (
                tuple(roundtrip.fortran_files)
                if roundtrip
                else tuple(sorted(fortran_routines[name]))
            )
            python_files = tuple(sorted(set(python_routines.get(name, []))))
            if roundtrip and roundtrip.python_files:
                python_files = tuple(
                    sorted(
                        set(python_files)
                        | {normalize_python_relative(path) for path in roundtrip.python_files}
                    )
                )
            source = "roundtrip+ast" if roundtrip else "ast"
            candidates.append(
                ExtendedRoutineCandidate(
                    name=name,
                    fortran_files=fortran_files,
                    python_files=python_files,
                    source=source,
                )
            )
        extended.append((item, candidates))
    return extended
