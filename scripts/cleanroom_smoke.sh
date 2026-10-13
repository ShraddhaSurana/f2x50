#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
corpus_root="${1:-/tmp/f2x50-corpus}"

cd "$repo_root"
python scripts/record_environment.py
python scripts/validate.py
bash clone_corpus.sh --destination "$corpus_root" --repo roots-fortran
bash clone_corpus.sh --destination "$corpus_root" --repo roots-fortran --verify-only --check-metrics
./harness/build_fortran_stubs.sh
python scripts/run_reference_example.py --corpus-root "$corpus_root"
