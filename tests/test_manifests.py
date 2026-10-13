from __future__ import annotations

import csv
import importlib.util
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    spec = importlib.util.spec_from_file_location("f2x50_validate", ROOT / "scripts/validate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "manifests/repositories.csv").open(newline="", encoding="utf-8") as handle:
            cls.repositories = list(csv.DictReader(handle))
        with (ROOT / "manifests/probes.csv").open(newline="", encoding="utf-8") as handle:
            cls.probes = list(csv.DictReader(handle))
        with (ROOT / "manifests/source_information.csv").open(newline="", encoding="utf-8") as handle:
            cls.source_information = list(csv.DictReader(handle))

    def test_release_cardinality(self) -> None:
        self.assertEqual(len(self.repositories), 50)
        self.assertEqual(len(self.probes), 559)
        self.assertEqual(len(self.source_information), 559)

    def test_every_probe_has_verified_source_information(self) -> None:
        self.assertEqual(
            {row["probe_id"] for row in self.probes},
            {row["probe_id"] for row in self.source_information},
        )
        self.assertEqual({row["audit_status"] for row in self.source_information}, {"verified"})

    def test_source_evidence_totals(self) -> None:
        self.assertEqual(
            Counter(row["oracle_kind"] for row in self.source_information),
            {
                "original-file-plus-driver": 444,
                "extracted-source": 8,
                "inline-reimplementation": 73,
                "synthetic-fixture": 34,
            },
        )

    def test_tier_balance(self) -> None:
        self.assertEqual(Counter(row["tier"] for row in self.repositories), {"low": 20, "medium": 20, "complex": 10})
        self.assertEqual(Counter(row["tier"] for row in self.probes), {"low": 203, "medium": 199, "complex": 157})

    def test_direct_source_repository_coverage(self) -> None:
        repository_by_probe = {row["probe_id"]: row["repository"] for row in self.probes}
        direct = Counter(
            repository_by_probe[row["probe_id"]]
            for row in self.source_information
            if row["oracle_kind"] == "original-file-plus-driver"
        )
        self.assertEqual(len(direct), 50)
        self.assertTrue(all(count >= 5 for count in direct.values()))

        direct_symbols = {}
        for row in self.source_information:
            if row["oracle_kind"] != "original-file-plus-driver":
                continue
            repository = repository_by_probe[row["probe_id"]]
            direct_symbols.setdefault(repository, set()).add(
                (row["upstream_path"], row["upstream_symbol"])
            )
        self.assertEqual(sum(len(symbols) for symbols in direct_symbols.values()), 130)
        self.assertEqual(sum(len(symbols) >= 2 for symbols in direct_symbols.values()), 49)

    def test_standard_validator(self) -> None:
        validator = load_validator()
        self.assertEqual(validator.validate(ROOT), [])

    def test_clean_metric_totals(self) -> None:
        self.assertEqual(sum(int(row["fortran_files"]) for row in self.repositories), 12_116)
        self.assertEqual(sum(int(row["fortran_loc"]) for row in self.repositories), 6_569_806)


if __name__ == "__main__":
    unittest.main()
