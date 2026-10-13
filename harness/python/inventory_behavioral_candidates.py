from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from behavioral_inventory import (
    DEFAULT_TARGET_ROOT,
    DEFAULT_FORTRAN_CORPUS_ROOT,
    inventories_to_json,
    inventory_matching_repos,
    render_selection_markdown,
    select_top_repos,
    write_inventory_csv,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory matching Fortran corpus repositories and Python target repositories, "
            "then select the most promising routine-level agreement candidates."
        )
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=DEFAULT_FORTRAN_CORPUS_ROOT,
        help="Path to the Fortran corpus root.",
    )
    parser.add_argument(
        "--target-root",
        type=Path,
        default=DEFAULT_TARGET_ROOT,
        help="Path to the Python target root.",
    )
    parser.add_argument(
        "--top-per-tier",
        type=int,
        default=5,
        help="Number of repos to select per tier.",
    )
    parser.add_argument(
        "--max-routines-per-repo",
        type=int,
        default=12,
        help="Maximum number of candidate routines to show per repo in markdown output.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path for the full inventory JSON output.",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        help="Optional path for the full inventory CSV output.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        help="Optional path for the selected-repos markdown output.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    inventories = inventory_matching_repos(
        corpus_root=args.corpus_root,
        target_root=args.target_root,
    )
    selected = select_top_repos(inventories, top_per_tier=args.top_per_tier)
    markdown = render_selection_markdown(
        selected,
        max_routines_per_repo=args.max_routines_per_repo,
    )

    print(markdown, end="")

    if args.json_out:
        args.json_out.write_text(inventories_to_json(inventories), encoding="utf-8")
    if args.csv_out:
        write_inventory_csv(args.csv_out, inventories)
    if args.markdown_out:
        args.markdown_out.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
