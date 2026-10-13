# Running f2x50 on Linux, macOS, and Windows

This guide separates three different claims:

1. **Release validation** checks the benchmark manifests, joins, identifiers, and fixed totals without downloading the source corpus.
2. **The clean-room smoke test** acquires one pinned repository, checks its measurements, builds the seven legacy `f2py` stubs, and runs one published source-to-target check end to end.
3. **A complete adapter replay** acquires all 50 pinned repositories and records an outcome for all 561 checks against an implementation supplied by the evaluator.

Passing the smoke test demonstrates that the evaluation path works. It does not mean that all 50 original projects build, that an entire repository was migrated, or that all 561 checks were run.

## Platform support

| Platform | Release validation | Native smoke test | Complete 561-check replay | Docker smoke test |
|---|---|---|---|---|
| Linux (Ubuntu/Debian) | Supported | Supported | Supported | Supported |
| macOS | Supported | Supported; recorded on ARM64 | Supported with GNU Fortran and Open MPI | Supported through Docker Desktop |
| Windows | Use WSL2 | Use WSL2 | Use WSL2 | Supported through Docker Desktop with Linux containers |
| Native Windows PowerShell/CMD | Metadata-only Python commands may work | Not supported | Not supported | Use Docker Desktop |

The executable harness is POSIX-oriented: it uses Bash scripts, Unix utilities, POSIX paths, temporary executables, GNU Fortran, and `mpifort`. Native Windows execution is therefore not a supported release configuration. [WSL2](https://learn.microsoft.com/windows/wsl/install) provides the supported Windows route by running the Linux instructions unchanged. Keep the checkout in the WSL Linux filesystem rather than under `/mnt/c` for better filesystem behavior.

## Common release validation

Run all commands from the root of the `f2x50` repository. Record the exact revision first:

```bash
git rev-parse HEAD
git status --short
```

For a release replay, use a clean checkout of the intended release commit. The validator itself requires only Python's standard library:

```bash
python scripts/validate.py
python -m unittest discover -s tests -v
python scripts/summarize.py
```

The expected release totals are 50 repositories and 561 checks. The unit-test suite currently contains eight tests.

## Linux

### Install the native toolchain

On Ubuntu or Debian:

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  git \
  build-essential \
  gfortran \
  python3 \
  python3-dev \
  python3-venv \
  libblas-dev \
  liblapack-dev \
  openmpi-bin \
  libopenmpi-dev
```

Create an isolated Python environment and install the pinned harness packages:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-harness.txt
python scripts/record_environment.py
```

Check that the complete replay toolchain is visible:

```bash
command -v git
command -v gfortran
command -v mpifort
command -v python3-config
```

### Run the native smoke test

Choose a work directory outside the Git checkout with enough space for the acquired corpus:

```bash
export F2X_RUN_ROOT=/absolute/path/to/f2x50-run
mkdir -p "$F2X_RUN_ROOT"
set -o pipefail
bash scripts/cleanroom_smoke.sh "$F2X_RUN_ROOT/smoke-corpus" \
  2>&1 | tee "$F2X_RUN_ROOT/native-smoke.log"
```

The command must exit with status zero. Display the final assertion with:

```bash
grep -n '"passed": true' "$F2X_RUN_ROOT/native-smoke.log"
```

`grep -q` may instead be used for scripting, but it deliberately prints nothing; status zero means that the text was found.

## macOS

The recorded native replay used macOS ARM64, CPython 3.13, and Homebrew GNU Fortran. Install Apple's Command Line Tools and the required [Homebrew](https://docs.brew.sh/Installation) packages:

```bash
xcode-select --install
brew install gcc open-mpi python@3.13
```

Homebrew supplies `gfortran` through the `gcc` formula and `mpifort` through the `open-mpi` formula. Put the versioned Python's unversioned command links first for this shell:

```bash
export PATH="$(brew --prefix python@3.13)/libexec/bin:$PATH"
```

Create the environment and run the same validation and smoke sequence:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-harness.txt
python scripts/record_environment.py

python scripts/validate.py
python -m unittest discover -s tests -v

export F2X_RUN_ROOT=/absolute/path/to/f2x50-run
mkdir -p "$F2X_RUN_ROOT"
set -o pipefail
bash scripts/cleanroom_smoke.sh "$F2X_RUN_ROOT/smoke-corpus" \
  2>&1 | tee "$F2X_RUN_ROOT/native-smoke.log"
grep -n '"passed": true' "$F2X_RUN_ROOT/native-smoke.log"
```

Both Apple Silicon and Intel users should use packages built for their host architecture. Do not mix an x86 Python environment with ARM Homebrew packages, or the reverse.

## Windows through WSL2

Native Windows is not supported for the compiled harness. On Windows 10 version 2004 or newer, or Windows 11, open an elevated PowerShell window and install WSL with Ubuntu:

```powershell
wsl --install -d Ubuntu
wsl --update
wsl --status
wsl -l -v
```

Restart Windows if requested, open the Ubuntu application, create the Linux user when prompted, and clone or copy the benchmark into the WSL Linux filesystem. From the Ubuntu Bash shell, follow the Linux instructions above beginning with `sudo apt-get update`.

All benchmark commands, environment variables, paths, and virtual-environment activation then use their Linux forms. Do not translate the Bash commands into PowerShell.

## Docker smoke test on Linux, macOS, or Windows

The supplied image is a Linux clean room based on `python:3.13-slim-bookworm`. It runs the one-repository smoke test automatically. It does not run the complete 561-check adapter replay.

On Linux, use Docker Engine or Docker Desktop. On macOS, use [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/). On Windows, use [Docker Desktop's WSL2 backend](https://docs.docker.com/desktop/features/wsl/) and select Linux containers.

Run these commands from the repository root:

```bash
docker build --pull --no-cache -t f2x50-linux-smoke:latest .
docker image inspect f2x50-linux-smoke:latest --format '{{.Id}}'
docker run --rm f2x50-linux-smoke:latest
```

The final JSON object must contain:

```json
"passed": true
```

If `docker run` says that it cannot find `f2x50-linux-smoke:latest` locally and then reports pull access denied, the local build did not create the tagged image in the Docker context used by the run. Re-run the build from the repository root and use the same Docker user, context, and `sudo` policy for both commands. This is a local image; no registry login is required.

## Acquire all 50 pinned repositories

The acquisition script's default destination is flat, while the reference adapter expects the source corpus under `<tier>/<directory>`. For a complete replay, acquire each entry directly into its tier directory:

```bash
export F2X_RUN_ROOT=/absolute/path/to/f2x50-run
export F2X_FORTRAN_CORPUS_ROOT="$F2X_RUN_ROOT/full-corpus"

mkdir -p \
  "$F2X_FORTRAN_CORPUS_ROOT/low" \
  "$F2X_FORTRAN_CORPUS_ROOT/medium" \
  "$F2X_FORTRAN_CORPUS_ROOT/complex"

set -e
while IFS=, read -r benchmark_id tier repository directory remainder
do
  bash clone_corpus.sh \
    --destination "$F2X_FORTRAN_CORPUS_ROOT/$tier" \
    --repo "$repository" \
    --check-metrics
done < <(tail -n +2 manifests/repositories.csv)
```

Recheck all pins and measurements without fetching:

```bash
while IFS=, read -r benchmark_id tier repository directory remainder
do
  bash clone_corpus.sh \
    --destination "$F2X_FORTRAN_CORPUS_ROOT/$tier" \
    --repo "$repository" \
    --verify-only \
    --check-metrics
done < <(tail -n +2 manifests/repositories.csv)
```

The aggregate manifest totals are 12,116 Git-tracked Fortran files and 6,569,806 physical lines.

## Supply the implementation being evaluated

The benchmark release does not include a complete set of translated targets. Supply the Python implementations being evaluated and set:

```bash
export F2X_TARGET_ROOT=/absolute/path/to/python-targets
```

The reference adapter expects this structure:

```text
$F2X_TARGET_ROOT/<tier>/<repository>/generated_python/src/
```

Install any additional dependencies declared by those targets into the active environment. `requirements-harness.txt` covers the harness, not arbitrary dependencies introduced by a migration method.

Check both layouts before starting:

```bash
python - <<'PY'
import csv
import os
from pathlib import Path

source_root = Path(os.environ["F2X_FORTRAN_CORPUS_ROOT"])
target_root = Path(os.environ["F2X_TARGET_ROOT"])

with Path("manifests/repositories.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))

missing_sources = [
    source_root / row["tier"] / row["directory"]
    for row in rows
    if not (source_root / row["tier"] / row["directory"]).is_dir()
]
missing_targets = [
    target_root / row["tier"] / row["repository"] / "generated_python" / "src"
    for row in rows
    if not (
        target_root / row["tier"] / row["repository"] / "generated_python" / "src"
    ).is_dir()
]

print(f"Source repositories found: {50 - len(missing_sources)}/50")
print(f"Target repositories found: {50 - len(missing_targets)}/50")
for label, missing in (("source", missing_sources), ("target", missing_targets)):
    if missing:
        print(f"Missing {label} paths:")
        print("\n".join(map(str, missing)))
if missing_sources or missing_targets:
    raise SystemExit(1)
PY
```

## Run and verify all 561 checks

```bash
mkdir -p "$F2X_RUN_ROOT/results"
set -o pipefail
python harness/python/run_corpus_verification.py \
  --json-out "$F2X_RUN_ROOT/results/results.json" \
  --markdown-out "$F2X_RUN_ROOT/results/report.md" \
  2>&1 | tee "$F2X_RUN_ROOT/full-run.log"
```

The runner records repository-level exceptions as explicit per-check results, so its process exit status alone is not enough. Verify the fixed denominator and count execution errors:

```bash
python - <<'PY'
import json
import os
from collections import Counter
from pathlib import Path

path = Path(os.environ["F2X_RUN_ROOT"]) / "results/results.json"
repositories = json.loads(path.read_text(encoding="utf-8"))
checks = [check for repository in repositories for check in repository["checks"]]
statuses = Counter(check["status"] for check in checks)

print(f"Repositories recorded: {len(repositories)}")
print(f"Checks recorded:       {len(checks)}")
print(f"Statuses:              {dict(statuses)}")

if len(repositories) != 50:
    raise SystemExit("expected 50 repository results")
if len(checks) != 561:
    raise SystemExit("expected 561 check results")
if statuses.get("error", 0):
    raise SystemExit(f"{statuses['error']} checks did not execute successfully")
PY
```

Interpret the statuses as follows:

- `pass`: the supplied target agreed with the source-side contract.
- `fail`: both sides executed, but their behavior disagreed.
- `error`: the check could not execute, for example because compilation, import, dependency, or target invocation failed.

For infrastructure verification, require exactly 50 repositories, exactly 561 results, and no unexpected execution errors. For a claim that a migration passes the benchmark completely, require all 561 statuses to be `pass`. Behavioral mismatches are benchmark findings, not harness crashes, and must not be omitted from the denominator.

## What to retain with a reported replay

Record or archive:

- the f2x50 release version and Git commit;
- `python scripts/record_environment.py` output;
- host operating system and architecture;
- Docker version and image ID when using Docker;
- corpus verification output;
- the JSON result file, Markdown report, and console log;
- dependencies and version of the evaluated target; and
- whether the run was native Linux, native macOS, WSL2, or a Linux container.

The release smoke-test evidence is recorded in [`cleanroom-replay.md`](cleanroom-replay.md). Probe semantics and adapter requirements are described in [`probes.md`](probes.md).
