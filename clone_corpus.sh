#!/usr/bin/env bash
# Acquire or verify the exact upstream revisions that define f2x50.
#
# Examples:
#   bash clone_corpus.sh
#   bash clone_corpus.sh /path/to/corpus
#   bash clone_corpus.sh --repo roots-fortran --check-metrics
#   bash clone_corpus.sh --destination /path/to/corpus --verify-only --check-metrics

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="$repo_root/manifests/repositories.csv"
destination="$repo_root/corpus"
destination_set=false
verify_only=false
check_metrics=false
selected_repositories=()

usage() {
    cat <<'EOF'
Usage: bash clone_corpus.sh [destination] [options]

Options:
  --destination DIR  Acquire repositories under DIR (default: ./corpus).
  --manifest FILE    Read repository pins from FILE.
  --repo NAME        Acquire or verify only NAME; may be repeated.
  --verify-only      Do not fetch; verify existing checkouts.
  --check-metrics    Recompute tracked Fortran file and source-line counts.
  -h, --help         Show this help.

Without --repo, all 50 manifest entries are processed. Repositories are
checked out at their recorded full Git SHAs in detached-HEAD state.
EOF
}

while (($#)); do
    case "$1" in
        --destination)
            [[ $# -ge 2 ]] || { echo "--destination requires a directory" >&2; exit 2; }
            destination="$2"
            destination_set=true
            shift 2
            ;;
        --manifest)
            [[ $# -ge 2 ]] || { echo "--manifest requires a file" >&2; exit 2; }
            manifest="$2"
            shift 2
            ;;
        --repo)
            [[ $# -ge 2 ]] || { echo "--repo requires a repository name" >&2; exit 2; }
            selected_repositories+=("$2")
            shift 2
            ;;
        --verify-only)
            verify_only=true
            shift
            ;;
        --check-metrics)
            check_metrics=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [[ "$destination_set" == true ]]; then
                echo "destination supplied more than once: $1" >&2
                exit 2
            fi
            destination="$1"
            destination_set=true
            shift
            ;;
    esac
done

[[ $# -eq 0 ]] || { echo "unexpected arguments: $*" >&2; exit 2; }
[[ -f "$manifest" ]] || { echo "manifest not found: $manifest" >&2; exit 2; }
command -v git >/dev/null || { echo "git is required" >&2; exit 2; }

is_selected() {
    local candidate="$1"
    local selected
    if ((${#selected_repositories[@]} == 0)); then
        return 0
    fi
    for selected in "${selected_repositories[@]}"; do
        [[ "$selected" == "$candidate" ]] && return 0
    done
    return 1
}

contains_name() {
    local candidate="$1"
    shift
    local item
    for item in "$@"; do
        [[ "$item" == "$candidate" ]] && return 0
    done
    return 1
}

verify_metrics() {
    local checkout="$1"
    local repository="$2"
    local expected_files="$3"
    local expected_lines="$4"
    local relative
    local actual_files=0
    local actual_lines=0
    local start
    local chunk_lines
    local source_paths=()

    if [[ -n "$(git -C "$checkout" status --porcelain --untracked-files=no)" ]]; then
        echo "$repository: tracked working-tree changes prevent metric verification" >&2
        return 1
    fi

    while IFS= read -r -d '' relative; do
        case "$relative" in
            *.f|*.F|*.for|*.FOR|*.f90|*.F90|*.f95|*.F95|*.f03|*.F03|*.f08|*.F08)
                source_paths+=("$checkout/$relative")
                actual_files=$((actual_files + 1))
                ;;
        esac
    done < <(git -C "$checkout" ls-files -z)

    for ((start = 0; start < actual_files; start += 200)); do
        chunk_lines="$(awk 'END { print NR }' "${source_paths[@]:start:200}")"
        actual_lines=$((actual_lines + chunk_lines))
    done

    if [[ "$actual_files" -ne "$expected_files" || "$actual_lines" -ne "$expected_lines" ]]; then
        echo "$repository: files/lines ($actual_files, $actual_lines) != manifest ($expected_files, $expected_lines)" >&2
        return 1
    fi
}

mkdir -p "$destination"
seen_repositories=()
processed=0

exec 3<"$manifest"
IFS= read -r _header <&3
while IFS=, read -r benchmark_id tier repository directory upstream_url revision revision_date fortran_files fortran_loc domain license_spdx license_status license_evidence <&3; do
    [[ -n "$benchmark_id" ]] || continue
    license_evidence="${license_evidence%$'\r'}"
    is_selected "$repository" || continue
    seen_repositories+=("$repository")

    checkout="$destination/$directory"
    if [[ "$verify_only" == false ]]; then
        if [[ -e "$checkout" && ! -d "$checkout/.git" ]]; then
            if [[ ! -d "$checkout" || -n "$(ls -A "$checkout" 2>/dev/null)" ]]; then
                echo "refusing to overwrite non-empty non-Git path: $checkout" >&2
                exit 1
            fi
        fi
        mkdir -p "$checkout"
        if [[ ! -d "$checkout/.git" ]]; then
            git -c init.defaultBranch=main init "$checkout" >/dev/null
            git -C "$checkout" remote add origin "$upstream_url"
        else
            git -C "$checkout" remote set-url origin "$upstream_url"
        fi
        echo "[$benchmark_id] fetching $repository @ ${revision:0:12}"
        # Public HTTPS acquisition must not be silently rewritten to a user's
        # SSH GitHub configuration, which can fail in clean environments.
        GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
            git -C "$checkout" fetch --depth 1 origin "$revision"
        git -C "$checkout" checkout --detach FETCH_HEAD >/dev/null
    elif [[ ! -d "$checkout/.git" ]]; then
        echo "$repository: checkout not found at $checkout" >&2
        exit 1
    fi

    actual_revision="$(git -C "$checkout" rev-parse HEAD)"
    if [[ "$actual_revision" != "$revision" ]]; then
        echo "$repository: expected $revision, found $actual_revision" >&2
        exit 1
    fi
    if [[ "$check_metrics" == true ]]; then
        verify_metrics "$checkout" "$repository" "$fortran_files" "$fortran_loc"
    fi
    if [[ "$license_status" != "declared" ]]; then
        echo "  licence status: $license_status ($license_spdx); consult docs/licensing.md"
    fi
    echo "  verified $repository @ ${revision:0:12}"
    processed=$((processed + 1))
done
exec 3<&-

for requested in "${selected_repositories[@]}"; do
    if ((${#seen_repositories[@]} == 0)) || ! contains_name "$requested" "${seen_repositories[@]}"; then
        echo "unknown repository: $requested" >&2
        exit 2
    fi
done

echo "Corpus acquisition complete: $processed repositories verified under $destination"
