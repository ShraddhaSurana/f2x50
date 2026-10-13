#!/usr/bin/env python3
"""Emit machine-readable toolchain information for a replay report."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys


def version(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    output = result.stdout or result.stderr
    return output.splitlines()[0].strip() if output else None


def main() -> None:
    packages = {}
    for name in ("numpy", "meson", "ninja"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    record = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.splitlines()[0],
        "git": version(["git", "--version"]),
        "gfortran": version(["gfortran", "--version"]),
        "packages": packages,
    }
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
