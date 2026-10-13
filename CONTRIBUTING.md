# Contributing

Bug reports and corrections are welcome. Please include the affected benchmark or probe identifier, exact upstream revision, evidence for the correction, and whether the change would alter a published result.

Before submitting a change, run:

```bash
python scripts/validate.py
python -m unittest discover -s tests
```

Published releases are immutable research objects. Metadata corrections, revision changes, probe additions, changed inputs, or changed tolerances require an entry in `CHANGELOG.md` and a new version. Do not commit upstream corpus checkouts, generated translations, compiler modules, shared libraries, evaluation results, or secrets.

By contributing code, you agree that it is licensed under Apache-2.0. By contributing manifest records, documentation, or original figures, you agree that they are licensed under CC BY 4.0.
