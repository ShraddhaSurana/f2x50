# Manifest schema

## Repository records

`manifests/repositories.csv` has one row per upstream project. `benchmark_id` is the stable f2x50 identity; `repository` is the name used by the harness; and `directory` is the checkout directory. `revision` is a full Git SHA and `revision_date` is informational metadata, not a floating selection rule.

`fortran_files` and `fortran_loc` follow the clean-tree measurement policy in `methodology.md`. `license_spdx` records an SPDX expression where one can be asserted, while `license_status` distinguishes an explicit declaration from a pin with no explicit licence. `license_evidence` gives the path or basis used in the review.

## Probe records

`manifests/probes.csv` has one row per planned behavioral check. `probe_id` is stable within this release. `case_name` is a human-readable routine or case label; it is not necessarily globally unique. `comparison_mode` selects one of six comparison families. `definition_file` points to executable source containing the exact input and acceptance rule.

`manifests/source_information.csv` joins one-to-one with the probe catalogue. `oracle_kind` distinguishes direct compilation of a pinned file, a text-checked extraction, a checked-in `f2py` wrapper, an inline reimplementation, and a synthetic fixture. Upstream path/symbol/line fields locate the pinned implementation when one is claimed. Harness path/line fields always identify the executable definition. `source_note` records how the locator was established or why no exact upstream procedure is claimed; it is not a target outcome or a claim of independent review.

Machine-readable JSON Schemas are provided in `schemas/`. CSV stores integer fields lexically, so applications should coerce `fortran_files` and `fortran_loc` before applying the JSON Schema.
