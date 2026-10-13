# Licensing and upstream code

The f2x50 repository contains three legally distinct categories of material:

1. Scripts and harness code authored for f2x50 are licensed under Apache-2.0.
2. Original manifests, documentation, and figures are licensed under CC BY 4.0.
3. The 50 upstream repositories are not redistributed here and remain governed by their own licences.

`manifests/repositories.csv` records the licence evidence found at each exact pin. SPDX expressions summarize that evidence but are not legal advice and do not replace the upstream text.

The audit found no explicit licence file or permission notice for `ABAQUS` or `MPM3D-F90` at their pinned revisions. `Cmathtuts` has a root GPL-3.0 licence text but its README states that individual examples may have their own licences. These three entries are therefore recorded as `NOASSERTION`. Public visibility does not make code open source or grant redistribution permission. The acquisition script can fetch a public repository for local research, but users remain responsible for determining whether their intended use is permitted.

WPS uses the WRF public-domain notice rather than a standard SPDX licence identifier and is recorded as `LicenseRef-WRF-Public-Domain`. Projects with dual or multiple licensing alternatives retain the complete expression in the manifest.

If an upstream licence changes after the pin, the licence at the benchmark revision remains the relevant evidence for that snapshot. Corrections should be proposed with a path and commit-specific citation.

## Release policy for the three `NOASSERTION` pins

Version 0.2 retains all three repositories as origin-only pins. The benchmark stores metadata, URLs, revisions, measurements, and independently authored contracts; it does not redistribute their upstream source. This preserves the fixed 50-repository composition without describing the three projects as open source. Acquisition remains opt-in, and users are responsible for determining whether their intended local use, translation, or redistribution is permitted.

| Policy | Benchmark impact | Risk |
|---|---|---|
| Retain all three as reference-only pins | Preserves the current 50-repository composition and IDs. Acquisition remains opt-in, and users must not redistribute the fetched code through f2x50. | Reviewers may question the phrase “public benchmark” and whether migration/translation is permitted for the two no-licence pins. |
| Replace the two no-licence pins; retain `Cmathtuts` as ambiguous | Requires new repositories, probes, totals, figures, IDs, and paper numbers before release. | Lowest avoidable licensing risk while preserving most of the current design. |
| Replace all three `NOASSERTION` pins | Same version-changing work for three entries. | Cleanest release story and the strongest basis for describing every pin as openly reusable. |
| Obtain explicit permission from the upstream owners | Preserves composition if permission covers acquisition, analysis, derived translations, and publication of benchmark metadata/contracts. | Timing and scope of permission may be uncertain; archive the written permission with the release records. |

Repository replacement is outside the version 0.2 release policy. Any future change to a pin or probe would define a new benchmark version and require recomputing every aggregate and regenerating the paper.
