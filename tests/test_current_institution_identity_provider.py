from __future__ import annotations

import socket
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import current_institution_identity_provider as provider  # noqa: E402
from current_procurement_contracts import (  # noqa: E402
    RawCurrentRupCandidate,
    SourceKind,
    SourceMaturity,
    SourceProvenance,
    validate_institution_identity_provider_result,
)
from procurement_identity_resolution import EvidenceRecord  # noqa: E402


VERSION = "2026-08-17T00:00:00+00:00"


def provenance():
    return SourceProvenance(
        source_kind=SourceKind.CURRENT_SIRUP,
        source_locator="fixture.duckdb#sha256=abc",
        observed_at="2026-08-17T00:00:00+00:00",
        acquisition_id="run-1",
        raw_receipt_id="receipt-1",
        schema_version="1",
        source_maturity=SourceMaturity.BOUNDED_ACQUISITION_VERIFIED,
    )


def sirup(**overrides):
    values = dict(
        planned_procurement_id="100", source_rup_id="RUP-100",
        id_satker="00123", id_kldi="  KLDI-01  ",
        institution_name="Pusat Data", kldi_name="Kementerian Contoh",
        package_title="Pengadaan Server Data Center", budget=Decimal("1000000000"),
        procurement_type="Barang", procurement_method="Tender",
        selection_period="Januari", location="Jakarta", source_year=2026,
        provenance=provenance(),
    )
    values.update(overrides)
    return RawCurrentRupCandidate(**values)


def evidence(candidate_id="spse-1", **overrides):
    values = dict(
        candidate_id=candidate_id, package_name="Pengadaan Server Data Center",
        institution="Kementerian Contoh", satker="Pusat Data", year=2026,
        budget=1_000_000_000, procurement_method="Tender", location="Jakarta",
        category="Barang", evidence_type="LOCAL_FIXTURE",
        source_file="fixture.json", source_record_id=candidate_id,
        collected_at=VERSION, provenance="local bounded fixture",
    )
    values.update(overrides)
    return EvidenceRecord(**values)


class CurrentInstitutionIdentityProviderTests(unittest.TestCase):
    def build(self, rows=None, candidate=None):
        return provider.CurrentInstitutionIdentityProvider(
            candidate or sirup(), [evidence()] if rows is None else rows,
            dataset_version=VERSION,
        )

    def test_success_preserves_ids_provenance_and_passes_contract(self):
        identity_provider = self.build()
        result = identity_provider.resolve("00123")
        validate_institution_identity_provider_result(result)
        self.assertEqual(1, len(result.candidates))
        identity = result.candidates[0]
        self.assertEqual("00123", identity.id_satker)
        self.assertEqual("  KLDI-01  ", identity.id_kldi)
        self.assertEqual("Pusat Data", identity.institution_name)
        self.assertIs(identity.provenance, result.provenance)
        self.assertIs(identity.provenance, identity_provider.sirup_candidate.provenance)
        self.assertIn('"decision":"CONFIRMED_MATCH"', identity.resolution_evidence)

    def test_buyer_key_and_repeated_execution_are_deterministic(self):
        first = self.build().resolve("00123")
        second = self.build().resolve("00123")
        self.assertEqual(first, second)
        self.assertEqual(first.candidates[0].buyer_identity_key, second.candidates[0].buyer_identity_key)
        self.assertTrue(first.candidates[0].buyer_identity_key.startswith("sirup-institution-"))

    def test_ambiguous_tie_remains_unresolved(self):
        result = self.build([evidence("a"), evidence("b")]).resolve("00123")
        self.assertEqual((), result.candidates)
        self.assertTrue(result.no_result)

    def test_hard_conflict_fails_closed(self):
        result = self.build([evidence(institution="Pemerintah Kabupaten Lain")]).resolve("00123")
        self.assertEqual((), result.candidates)
        self.assertTrue(result.no_result)

    def test_name_only_evidence_cannot_authorize(self):
        row = evidence(
            package_name="", satker="", year=None, budget=None,
            procurement_method="", location="", category="",
        )
        result = self.build([row]).resolve("00123")
        self.assertEqual((), result.candidates)

    def test_missing_or_conflicting_identity_fails_closed(self):
        cases = (
            (sirup(id_satker=""), "00123"),
            (sirup(id_kldi=""), "00123"),
            (sirup(institution_name=""), "00123"),
            (sirup(), "123"),
        )
        for candidate, requested in cases:
            with self.subTest(requested=requested), self.assertRaises(
                provider.InstitutionIdentityProviderError
            ):
                self.build(candidate=candidate).resolve(requested)

    def test_no_network_access(self):
        with mock.patch.object(socket, "create_connection") as connect:
            self.build().resolve("00123")
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
