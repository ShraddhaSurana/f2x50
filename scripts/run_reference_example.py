#!/usr/bin/env python3
"""Run one published source-to-target check with the bundled Python example."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def load_target(path: Path):
    spec = importlib.util.spec_from_file_location("f2x50_example_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load target adapter {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--compiler", default="gfortran")
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if compiler is None:
        raise SystemExit(f"Fortran compiler not found: {args.compiler}")
    source = args.corpus_root / "roots-fortran" / "src" / "root_module.F90"
    if not source.is_file():
        raise SystemExit(f"acquire roots-fortran first; missing {source}")

    with tempfile.TemporaryDirectory(prefix="f2x50-example-") as temporary:
        executable = Path(temporary) / "root_probe"
        command = [
            compiler,
            "-cpp",
            "-O0",
            str(source),
            str(root / "examples/root_bisection_driver.f90"),
            "-o",
            str(executable),
        ]
        subprocess.run(command, check=True, cwd=temporary)
        completed = subprocess.run(
            [str(executable)], check=True, text=True, capture_output=True
        )
    source_root, source_value, source_flag = completed.stdout.split()
    source_values = (float(source_root), float(source_value), int(source_flag))

    target = load_target(root / "examples/root_bisection_target.py")
    target_values = target.bisection(lambda value: value * value - 2.0, 1.0, 2.0)
    absolute_error = abs(target_values[0] - source_values[0])
    passed = absolute_error <= 1.0e-6 and target_values[2] == source_values[2]
    result = {
        "probe_id": "f2x50-low-roots-fortran-001",
        "source": {
            "revision_file": "roots-fortran/src/root_module.F90",
            "root": source_values[0],
            "f_root": source_values[1],
            "status": source_values[2],
        },
        "target": {
            "adapter": "examples/root_bisection_target.py",
            "root": target_values[0],
            "f_root": target_values[1],
            "status": target_values[2],
        },
        "comparison": {"absolute_error": absolute_error, "atol": 1.0e-6},
        "passed": passed,
        "note": "Reference result for one published check; demonstrates the evaluation path without claiming a full repository migration.",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
