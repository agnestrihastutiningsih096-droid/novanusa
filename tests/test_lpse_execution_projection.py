import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from current_procurement_contracts import (  # noqa: E402
    RawExecutionCandidate,
    SourceKind,
    SourceMaturity,
    SourceProvenance,
)
from lpse_execution_projection import (  # noqa: E402
    LpseExecutionProjectionError,
    project_lpse_row_to_raw_execution_candidate,
)


class LpseExecutionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "lpse_name": "LPSE Kementerian Keuangan",
            "package_code": "39250011",
            "package_name": "Pencetakan Pita Cukai Desain Tahun 2025 dan 2026",
            "institution_name": "Kementerian Keuangan",
            "satker": "Direktorat Teknis",
            "hps_or_pagu": "891,2 M",
            "stage_or_status": "Paket Sudah Selesai",
            "method": "Penunjukan Langsung",
            "fiscal_year": "2026",
            "detail_url": "https://spse.inaproc.id/kemenkeu/nontender/39250011/pengumumanpl",
            "collected_at": "2026-08-19T00:00:00+00:00",
            "raw_file_path": r"data\evidence\lpse\raw\kemenkeu\2026\nontender\39250011\manifest.json",
            "evidence_level": "LPSE_PUBLIC_DETAIL_FOUND",
        }
        self.provenance = SourceProvenance(
            source_kind=SourceKind.LPSE,
            source_locator=self.row["detail_url"],
            observed_at=self.row["collected_at"],
            acquisition_id="lpse-acquisition-evidence-1",
            raw_receipt_id="lpse-raw-receipt-evidence-1",
            schema_version="lpse-detail-row-v1",
            source_maturity=SourceMaturity.DISCOVERED,
        )

    def project(self, row=None, provenance=None):
        return project_lpse_row_to_raw_execution_candidate(
            self.row if row is None else row,
            self.provenance if provenance is None else provenance,
        )

    def test_valid_row_maps_exact_fields_and_preserves_input(self):
        before = copy.deepcopy(self.row)
        candidate = self.project()

        self.assertIsInstance(candidate, RawExecutionCandidate)
        self.assertEqual("39250011", candidate.source_package_id)
        self.assertEqual(self.row["package_name"], candidate.package_title)
        self.assertEqual(self.row["institution_name"], candidate.institution_name_if_present)
        self.assertEqual(self.row["stage_or_status"], candidate.execution_stage)
        self.assertEqual(self.row["method"], candidate.procurement_method_if_present)
        self.assertEqual(2026, candidate.source_year)
        self.assertEqual(before, self.row)

    def test_package_identity_is_deterministic(self):
        first = self.project()
        second = self.project(copy.deepcopy(self.row))
        self.assertEqual("lpse:39250011", first.execution_id)
        self.assertEqual(first.execution_id, second.execution_id)

    def test_text_satker_and_absent_kldi_do_not_become_ids(self):
        candidate = self.project()
        self.assertIsNone(candidate.id_satker_if_present)
        self.assertIsNone(candidate.id_kldi_if_present)

    def test_ambiguous_localized_value_is_not_fabricated(self):
        self.assertIsNone(self.project().contract_value_if_present)

    def test_missing_required_identity_title_or_year_fails_closed(self):
        for field in ("package_code", "package_name", "fiscal_year"):
            row = dict(self.row)
            row[field] = ""
            with self.subTest(field=field), self.assertRaises(LpseExecutionProjectionError):
                self.project(row)

    def test_provenance_is_the_supplied_lpse_evidence(self):
        candidate = self.project()
        self.assertIs(self.provenance, candidate.provenance)
        self.assertIs(SourceKind.LPSE, candidate.source_kind)
        self.assertEqual(self.row["detail_url"], candidate.provenance.source_locator)
        self.assertEqual(self.row["collected_at"], candidate.provenance.observed_at)

        wrong_source = SourceProvenance(
            SourceKind.SPSE, self.row["detail_url"], self.row["collected_at"],
            "actual-acquisition", "actual-receipt", "v1", SourceMaturity.DISCOVERED,
        )
        with self.assertRaises(LpseExecutionProjectionError):
            self.project(provenance=wrong_source)
        with self.assertRaises(LpseExecutionProjectionError):
            project_lpse_row_to_raw_execution_candidate(self.row, None)

    def test_projection_does_not_validate_promote_or_persist(self):
        with (
            patch("current_procurement_contracts.validate_execution") as validate,
            patch("current_procurement_contracts.promote_observed_execution") as promote,
            patch("current_procurement_contracts._persist_decision") as persist,
        ):
            self.project()
        validate.assert_not_called()
        promote.assert_not_called()
        persist.assert_not_called()


if __name__ == "__main__":
    unittest.main()
