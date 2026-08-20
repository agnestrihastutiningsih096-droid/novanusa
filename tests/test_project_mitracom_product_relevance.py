from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import project_mitracom_product_relevance as projection  # noqa: E402
import demand_taxonomy_v1_classifier as taxonomy  # noqa: E402
import current_procurement_contracts as contracts  # noqa: E402


class ProductRelevanceProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary.name)
        # The projection must not create any file anywhere; fail the test if it does.
        self.existing_files = set(self.temporary_root.rglob("*"))

    def tearDown(self):
        self.temporary.cleanup()

    def assert_no_files_created_anywhere(self):
        leftovers = [path for path in self.temporary_root.rglob("*") if path not in self.existing_files]
        self.assertEqual([], leftovers)

    def test_deterministic_replay(self):
        corpus = [
            "Pengadaan Laptop dan Printer",
            "Pengadaan Jasa Konsultansi",
            "Pengadaan Server dan UPS",
            "Sewa Laptop",
            "Pengadaan Kabel Fiber Optik",
            "Tinta Printer",
            "unknown-package",
            "",
        ]
        first = tuple(projection.project_product_relevance(title) for title in corpus)
        for _ in range(100):
            self.assertEqual(first, tuple(projection.project_product_relevance(title) for title in corpus))

    def test_projection_classification_equals_direct_classify_demand(self):
        for title in ("Pengadaan Laptop dan Printer", "Sewa Laptop", "Tinta Printer", "Pengadaan Jasa Konsultansi", ""):
            projected = projection.project_product_relevance(title)
            classification = taxonomy.classify_demand(title)
            self.assertEqual(projected.demand_families, classification.demand_families)
            self.assertEqual(projected.taxonomy_version, classification.taxonomy_version)
            self.assertEqual(projected.taxonomy_sha256, classification.taxonomy_sha256)

    def test_laptop_and_printer_maps_to_existing_seed_ids(self):
        result = projection.project_product_relevance("Pengadaan Laptop dan Printer")
        self.assertEqual(("mitracom-laptop-general", "mitracom-printer-general"), result.matched_product_ids)
        for product_id in result.matched_product_ids:
            self.assertIn(product_id, projection.MITRACOM_SEED_PRODUCT_IDS)

    def test_consulting_service_does_not_fabricate_product_relevance(self):
        result = projection.project_product_relevance("Pengadaan Jasa Konsultansi")
        self.assertEqual((), result.demand_families)
        self.assertEqual((), result.matched_product_ids)

    def test_empty_and_unmatched_demand_produce_no_product_match(self):
        for title in ("", "unknown-package", "Balai Monitor SFR Kelas II"):
            result = projection.project_product_relevance(title)
            self.assertEqual((), result.matched_product_ids)

    def test_semantic_state_is_exactly_candidate_derived_signal_only(self):
        result = projection.project_product_relevance("Pengadaan Laptop dan Printer")
        self.assertEqual("CANDIDATE_DERIVED_SIGNAL_ONLY", result.semantic_state)
        self.assertEqual(projection.OUTPUT_SEMANTIC_STATE, result.semantic_state)

    def test_result_is_not_supplier_product_compatibility(self):
        result = projection.project_product_relevance("Pengadaan Laptop dan Printer")
        self.assertNotIsInstance(result, contracts.SupplierProductCompatibility)
        self.assertFalse(hasattr(result, "compatibility_state"))
        self.assertFalse(hasattr(result, "supplier_product_id"))

    def test_forbidden_authority_calls_never_occur(self):
        with mock.patch.object(contracts, "validate_compatibility", side_effect=AssertionError("validate_compatibility called")) as validate:
            with mock.patch.object(contracts, "promote_supplier_compatibility", side_effect=AssertionError("promote_supplier_compatibility called")) as promote:
                with mock.patch.object(contracts, "_persist_decision", side_effect=AssertionError("_persist_decision called")) as persist:
                    with mock.patch.object(contracts, "evaluate_outreach_eligibility", side_effect=AssertionError("evaluate_outreach_eligibility called")) as evaluate:
                        for title in ("Pengadaan Laptop dan Printer", "Pengadaan Jasa Konsultansi", ""):
                            projection.project_product_relevance(title)
                        validate.assert_not_called()
                        promote.assert_not_called()
                        persist.assert_not_called()
                        evaluate.assert_not_called()

    def test_no_decision_store_persistence(self):
        store_path = self.temporary_root / "decisions.json"
        with mock.patch.object(contracts, "_DECISION_STORE", contracts.ProcurementDecisionStore(store_path)):
            projection.project_product_relevance("Pengadaan Laptop dan Printer")
            projection.project_product_relevance("Pengadaan Jasa Konsultansi")
        self.assertFalse(store_path.exists())

    def test_no_network_credential_or_db_access(self):
        with mock.patch("socket.socket", side_effect=AssertionError("socket used")):
            with mock.patch("urllib.request.urlopen", side_effect=AssertionError("urlopen used")):
                with mock.patch("os.environ", {}):
                    with mock.patch("duckdb.connect", side_effect=AssertionError("duckdb used")):
                        projection.project_product_relevance("Pengadaan Laptop dan Printer")
        self.assert_no_files_created_anywhere()

    def test_taxonomy_sha256_is_frozen(self):
        result = projection.project_product_relevance("Pengadaan Laptop dan Printer")
        self.assertEqual(taxonomy.TAXONOMY_SHA256, result.taxonomy_sha256)
        self.assertEqual("3864ef756fc96aa5e0454335f0ac38154d3a3417a6e5300b781ed550f657ffe0", result.taxonomy_sha256)

    def test_mapping_uses_only_frozen_families_and_existing_seed_ids(self):
        for family, product_ids in projection.DEMAND_FAMILY_TO_MITRACOM_PRODUCT.items():
            self.assertIn(family, taxonomy.DEMAND_FAMILIES)
            for product_id in product_ids:
                self.assertIn(product_id, projection.MITRACOM_SEED_PRODUCT_IDS)

    def test_procurement_type_corroboration_only(self):
        # jenis_pengadaan is corroborative; it must never manufacture a family or product.
        result = projection.project_product_relevance("unknown", "Pengadaan Laptop")
        self.assertEqual((), result.demand_families)
        self.assertEqual((), result.matched_product_ids)
        known = projection.project_product_relevance("Laptop", "Jasa Lainnya")
        self.assertIn("mitracom-laptop-general", known.matched_product_ids)


if __name__ == "__main__":
    unittest.main()
