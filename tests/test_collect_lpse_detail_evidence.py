import argparse
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from scripts.collect_lpse_detail_evidence import (
    OUTPUT_COLUMNS,
    build_cli_routing_binding,
    extract_tables,
    main,
    parse_detail_fields,
    parse_kode_rup,
    routing_binding_from_args,
    select_registry_rows,
)
from scripts.kldi_lpse_routing import (
    KldiLpseRoutingStatus,
    LpseRegistryEvidence,
    SirupRoutingEvidence,
    build_kldi_lpse_routing_binding,
    validate_routing_authority,
)


DETAIL_HTML = """
<table>
  <tr><th>Kode Paket</th><td>123</td></tr>
  <tr>
    <th>Rencana Umum Pengadaan</th>
    <td><table><tr><th>Kode RUP</th><th>Nama Paket</th></tr><tr><td>456</td><td>Contoh</td></tr></table></td>
  </tr>
  <tr><th>Tahap Paket Saat Ini</th><td>Paket Sudah Selesai</td></tr>
  <tr><th>K/L/PD/Instansi Lainnya</th><td>Kementerian Keuangan</td></tr>
  <tr><th>Satuan Kerja</th><td>KANTOR PUSAT DIREKTORAT JENDERAL BEA DAN CUKAI</td></tr>
  <tr><th>Metode Pengadaan</th><td>Penunjukan Langsung</td></tr>
</table>
"""


class HTMLTableParserTests(unittest.TestCase):
    def test_simple_table_parsing_remains_valid(self) -> None:
        tables = extract_tables("<table><tr><th>Label</th><th>Value</th></tr><tr><td>A</td><td>B</td></tr></table>")

        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0].headers, ["Label", "Value"])
        self.assertEqual(tables[0].rows, [["A", "B"]])

    def test_nested_table_does_not_erase_outer_detail_rows(self) -> None:
        tables = extract_tables(DETAIL_HTML)
        cells = [cell for table in tables for row in [table.headers, *table.rows] for cell in row]

        self.assertIn("Satuan Kerja", cells)
        self.assertIn("KANTOR PUSAT DIREKTORAT JENDERAL BEA DAN CUKAI", cells)

    def test_parse_detail_fields_after_nested_table(self) -> None:
        fields = parse_detail_fields(DETAIL_HTML, "https://example.test/detail")

        self.assertEqual(fields["institution_name"], "Kementerian Keuangan")
        self.assertEqual(fields["satker"], "KANTOR PUSAT DIREKTORAT JENDERAL BEA DAN CUKAI")
        self.assertEqual(fields["stage_or_status"], "Paket Sudah Selesai")
        self.assertEqual(fields["method"], "Penunjukan Langsung")
        self.assertIn("satker", OUTPUT_COLUMNS)


class KodeRupExtractionTests(unittest.TestCase):
    LIVE_KODE_RUP = "61958830"
    # Minimal deterministic HTML mirroring the known live evidence structure:
    # a nested "Rencana Umum Pengadaan" table whose columns are
    # "Kode RUP" / "Nama Paket" / "Sumber Dana".
    RUP_HTML = """
    <table>
      <tr><th>Kode Paket</th><td>10778419000</td></tr>
      <tr>
        <th>Rencana Umum Pengadaan</th>
        <td>
          <table>
            <tr><th>Kode RUP</th><th>Nama Paket</th><th>Sumber Dana</th></tr>
            <tr><td>61958830</td><td>Perencanaan Irigasi</td><td>APBD</td></tr>
          </table>
        </td>
      </tr>
      <tr><th>Tahap Paket Saat Ini</th><td>Paket Sudah Selesai</td></tr>
      <tr><th>K/L/PD/Instansi Lainnya</th><td>Kab. Kolaka Utara</td></tr>
      <tr><th>Metode Pengadaan</th><td>Pengadaan Langsung</td></tr>
    </table>
    """

    def test_exact_label_extracts_exact_value(self):
        tables = extract_tables(self.RUP_HTML)
        self.assertEqual(self.LIVE_KODE_RUP, parse_kode_rup(tables))

    def test_parse_detail_fields_exposes_kode_rup(self):
        fields = parse_detail_fields(self.RUP_HTML, "https://example.test/detail")
        self.assertEqual(self.LIVE_KODE_RUP, fields["kode_rup"])

    def test_absent_kode_rup_yields_empty(self):
        html = "<table><tr><th>Kode Paket</th><td>1</td></tr></table>"
        self.assertEqual("", parse_kode_rup(extract_tables(html)))

    def test_blank_kode_rup_yields_empty(self):
        html = """
        <table>
          <tr><th>Kode RUP</th><th>Nama Paket</th></tr>
          <tr><td>   </td><td>Contoh</td></tr>
        </table>
        """
        self.assertEqual("", parse_kode_rup(extract_tables(html)))

    def test_nested_tables_do_not_erase_kode_rup(self):
        # Same as RUP_HTML: the Kode RUP value lives in a nested table.
        fields = parse_detail_fields(self.RUP_HTML, "https://example.test/detail")
        self.assertEqual(self.LIVE_KODE_RUP, fields["kode_rup"])
        self.assertEqual("Paket Sudah Selesai", fields["stage_or_status"])

    def test_unrelated_numeric_values_not_mistaken_for_kode_rup(self):
        html = """
        <table>
          <tr><th>Kode Paket</th><td>10778419000</td></tr>
          <tr><th>Nilai HPS</th><td>35000000</td></tr>
          <tr><th>Uraian</th><td>12345</td></tr>
        </table>
        """
        self.assertEqual("", parse_kode_rup(extract_tables(html)))

    def test_package_code_never_substituted_for_kode_rup(self):
        html = """
        <table>
          <tr><th>Kode Paket</th><td>10778419000</td></tr>
        </table>
        """
        fields = parse_detail_fields(html, "https://example.test/detail")
        # The parser treats the first row as column headers, so the label/value
        # row is not a data row; kode_rup must still be empty and must never be
        # filled from any package-code-like value.
        self.assertEqual("", fields["kode_rup"])

    def test_repeated_parsing_is_deterministic(self):
        first = parse_detail_fields(self.RUP_HTML, "https://example.test/detail")
        for _ in range(25):
            self.assertEqual(first, parse_detail_fields(self.RUP_HTML, "https://example.test/detail"))

    def test_existing_detail_fields_remain_unchanged(self):
        fields = parse_detail_fields(self.RUP_HTML, "https://example.test/detail")
        # Existing data-row label/value fields are unchanged by kode_rup extraction.
        # (Columnar nested-table rows are not label/value pairs, so package_name
        # stays empty in this fixture exactly as before the change.)
        self.assertEqual("", fields["package_name"])
        self.assertEqual("Kab. Kolaka Utara", fields["institution_name"])
        self.assertEqual("Paket Sudah Selesai", fields["stage_or_status"])
        self.assertEqual("Pengadaan Langsung", fields["method"])
        self.assertEqual("61958830", fields["kode_rup"])

    def test_output_columns_exposes_kode_rup_exactly_once(self):
        self.assertEqual(1, OUTPUT_COLUMNS.count("kode_rup"))

    def test_ambiguous_kode_rup_fails_closed(self):
        html = """
        <table>
          <tr><th>Kode RUP</th><th>Nama Paket</th></tr>
          <tr><td>11111111</td><td>A</td></tr>
          <tr><td>22222222</td><td>B</td></tr>
        </table>
        """
        with self.assertRaises(ValueError):
            parse_kode_rup(extract_tables(html))

    def test_duplicate_identical_kode_rup_is_not_ambiguous(self):
        html = """
        <table>
          <tr><th>Kode RUP</th><th>Nama Paket</th></tr>
          <tr><td>61958830</td><td>A</td></tr>
          <tr><td>61958830</td><td>B</td></tr>
        </table>
        """
        self.assertEqual("61958830", parse_kode_rup(extract_tables(html)))

    def test_live_evidence_fixture_extracts_known_value(self):
        # Read-only use of the known live evidence file (no network).
        from pathlib import Path

        live = Path(__file__).resolve().parents[1] / "data" / "evidence" / "lpse" / "raw" / "kolutkab" / "2026" / "nontender" / "10778419000" / "detail.html"
        if not live.exists():
            self.skipTest("live evidence fixture not present")
        fields = parse_detail_fields(live.read_text(encoding="utf-8"), "https://example.test/detail")
        self.assertEqual("61958830", fields["kode_rup"])

    def test_extraction_uses_no_network_credentials_db_or_authority(self):
        import os as _os
        import socket as _socket
        from unittest import mock as _mock

        import scripts.current_procurement_contracts as contracts

        with (
            _mock.patch.object(_socket, "socket", side_effect=AssertionError("socket used")),
            _mock.patch("urllib.request.urlopen", side_effect=AssertionError("urlopen used")),
            _mock.patch.dict(_os.environ, {}, clear=True),
            _mock.patch("duckdb.connect", side_effect=AssertionError("duckdb used")),
            _mock.patch.object(contracts.ProcurementDecisionStore, "append", side_effect=AssertionError("decision append used")),
            _mock.patch.object(contracts, "verify_realization_link", side_effect=AssertionError("verify_realization_link called")),
            _mock.patch.object(contracts, "validate_execution", side_effect=AssertionError("validate_execution called")),
            _mock.patch.object(contracts, "promote_observed_execution", side_effect=AssertionError("promote_observed_execution called")),
            _mock.patch.object(contracts, "validate_compatibility", side_effect=AssertionError("validate_compatibility called")),
            _mock.patch.object(contracts, "promote_supplier_compatibility", side_effect=AssertionError("promote_supplier_compatibility called")),
            _mock.patch.object(contracts, "evaluate_outreach_eligibility", side_effect=AssertionError("evaluate_outreach_eligibility called")),
            _mock.patch.object(contracts, "_persist_decision", side_effect=AssertionError("_persist_decision called")),
        ):
            fields = parse_detail_fields(self.RUP_HTML, "https://example.test/detail")
            self.assertEqual("61958830", fields["kode_rup"])


class RoutingSelectionTests(unittest.TestCase):
    ROUTE = "https://spse.inaproc.id/haltengkab"

    def setUp(self) -> None:
        self.sirup = SirupRoutingEvidence(
            canonical_kldi_id="D294",
            source_kldi_name="Kab. Halmahera Tengah",
            acquisition_run_id="run-1",
            receipt_chain_reference="receipt-1",
            receipt_chain_hash="sha256:receipt",
            source_version="sirup-v1",
            province="Maluku Utara",
            government_level="Kabupaten",
        )
        self.registry_evidence = LpseRegistryEvidence(
            lpse_name="LPSE Kabupaten Halmahera Tengah",
            official_lpse_url=self.ROUTE,
            registry_artifact_id="registry-1",
            registry_artifact_hash="sha256:registry",
            registry_version="registry-v1",
            province="Maluku Utara",
            government_level="Kabupaten",
        )
        self.active = build_kldi_lpse_routing_binding(self.sirup, [self.registry_evidence])
        self.registry = pd.DataFrame([
            {"nama_lpse": "LPSE Lain", "official_lpse_url": "https://spse.inaproc.id/lain"},
            {"nama_lpse": self.registry_evidence.lpse_name, "official_lpse_url": self.ROUTE},
        ])

    def assert_fails_closed(self, binding, registry=None) -> None:
        with self.assertRaises(ValueError):
            select_registry_rows(self.registry if registry is None else registry, 99, binding)

    def test_active_d294_route_selects_exact_registry_row_without_network(self) -> None:
        with patch("scripts.collect_lpse_detail_evidence.make_opener") as network_boundary:
            selected = select_registry_rows(self.registry, 1, self.active)

        self.assertEqual(self.active.status, KldiLpseRoutingStatus.ROUTING_ACTIVE)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["official_lpse_url"], self.ROUTE)
        self.assertEqual(selected[0]["nama_lpse"], "LPSE Kabupaten Halmahera Tengah")
        network_boundary.assert_not_called()

    def test_stale_binding_fails_closed(self) -> None:
        stale = validate_routing_authority(self.active, registry_version="registry-v2")
        self.assert_fails_closed(stale)

    def test_ambiguous_binding_fails_closed(self) -> None:
        ambiguous = build_kldi_lpse_routing_binding(self.sirup, [self.registry_evidence, self.registry_evidence])
        self.assert_fails_closed(ambiguous)

    def test_rejected_binding_fails_closed(self) -> None:
        rejected = build_kldi_lpse_routing_binding(self.sirup, [])
        self.assert_fails_closed(rejected)

    def test_tampered_binding_fails_closed(self) -> None:
        self.assert_fails_closed(replace(self.active, official_lpse_url="https://example.test/tampered"))

    def test_route_absent_from_registry_fails_closed(self) -> None:
        self.assert_fails_closed(self.active, self.registry.iloc[[0]].copy())

    def test_duplicate_exact_route_fails_closed(self) -> None:
        duplicate = pd.concat([self.registry, self.registry.iloc[[1]]], ignore_index=True)
        self.assert_fails_closed(self.active, duplicate)

    def test_no_routing_input_preserves_limit_and_selection_semantics(self) -> None:
        selected = select_registry_rows(self.registry, 1)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["nama_lpse"], "LPSE Kabupaten Halmahera Tengah")

    def test_routing_selection_does_not_add_identity_or_realization_semantics(self) -> None:
        selected = select_registry_rows(self.registry, 1, self.active)

        self.assertEqual(selected[0]["nama_lpse"], self.registry_evidence.lpse_name)
        self.assertNotIn("institution_name", selected[0])
        self.assertNotIn("satker", selected[0])
        self.assertNotIn("realization", selected[0])


class CliRoutingBindingTests(unittest.TestCase):
    ROUTE = "https://spse.inaproc.id/haltengkab"

    def sirup_result(self, *, candidates=None):
        if candidates is None:
            candidates = (SimpleNamespace(id_kldi="D294", kldi_name="Kab. Halmahera Tengah"),)
        return SimpleNamespace(candidates=candidates, provenance=SimpleNamespace(
            acquisition_id="20260817T043259Z-2026-100rows",
            raw_receipt_id="60ccad916491f8100fe9a14340f0cd4609ca54f0e4f647ad97207ef73ac6b840",
            observed_at="2026-08-17T04:33:00.921Z",
        ))

    def registry(self):
        return pd.DataFrame([{
            "nama_lpse": "LPSE Kabupaten Halmahera Tengah",
            "official_lpse_url": self.ROUTE,
            "provinsi": "Maluku Utara",
            "kategori_instansi": "Pemerintah Kabupaten",
        }])

    def metadata(self):
        digest = "011d54c98b82b035732565715a8b732cb8e315b602a2d6c13f98f545485930f7"
        return {"registry_artifact_id": "novanusa:lpse-registry:csv", "registry_artifact_hash": digest, "registry_version": f"sha256:{digest}"}

    def build(self, *, result=None, registry=None, metadata=None):
        with (
            patch("scripts.collect_lpse_detail_evidence.acquire_validated_sirup", return_value=result or self.sirup_result()),
            patch("scripts.collect_lpse_detail_evidence.load_registry_artifact_metadata", return_value=metadata or self.metadata()),
            patch("scripts.collect_lpse_detail_evidence.pd.read_csv", return_value=self.registry() if registry is None else registry),
        ):
            return build_cli_routing_binding("D294", Path("validated-run"))

    def test_explicit_d294_builds_active_canonical_binding_and_exact_route(self):
        binding = self.build()
        self.assertIs(binding.status, KldiLpseRoutingStatus.ROUTING_ACTIVE)
        self.assertEqual(binding.canonical_kldi_id, "D294")
        self.assertEqual(binding.official_lpse_url, self.ROUTE)
        self.assertEqual(binding.sirup_acquisition_run_id, "20260817T043259Z-2026-100rows")
        self.assertEqual(binding.sirup_source_version, "sirup-authenticated-2026-08-17")
        self.assertEqual(binding.registry_version, self.metadata()["registry_version"])

    def test_main_passes_constructed_binding_to_collector(self):
        binding = self.build()
        args = argparse.Namespace(
            routing_kldi_id="D294", sirup_run_directory=Path("validated-run"),
            parsed_csv=Path("parsed.csv"), summary=Path("summary.json"), output=Path("output.xlsx"),
        )
        with (
            patch("scripts.collect_lpse_detail_evidence.parse_args", return_value=args),
            patch("scripts.collect_lpse_detail_evidence.routing_binding_from_args", return_value=binding),
            patch("scripts.collect_lpse_detail_evidence.collect", return_value=([], {})) as collector,
            patch("scripts.collect_lpse_detail_evidence.write_csv"), patch("scripts.collect_lpse_detail_evidence.save_text"),
            patch("scripts.collect_lpse_detail_evidence.write_excel"),
        ):
            main()
        collector.assert_called_once_with(args, binding)

    def test_mismatched_or_stale_routing_authority_fails_closed(self):
        with (
            patch("scripts.collect_lpse_detail_evidence.acquire_validated_sirup", return_value=self.sirup_result()),
            patch("scripts.collect_lpse_detail_evidence.load_registry_artifact_metadata", side_effect=ValueError("stale registry")),
            patch("scripts.collect_lpse_detail_evidence.pd.read_csv") as registry_read,
            self.assertRaises(ValueError),
        ):
            build_cli_routing_binding("D294", Path("validated-run"))
        registry_read.assert_not_called()

    def test_ambiguous_or_missing_sirup_evidence_fails_closed(self):
        cases = ((), (
            SimpleNamespace(id_kldi="D294", kldi_name="Kab. Halmahera Tengah"),
            SimpleNamespace(id_kldi="D294", kldi_name="Kab. Different"),
        ))
        for candidates in cases:
            with self.subTest(candidates=candidates), self.assertRaises(ValueError):
                self.build(result=self.sirup_result(candidates=candidates))

    def test_no_explicit_routing_input_preserves_non_routing_behavior(self):
        args = argparse.Namespace(routing_kldi_id=None, sirup_run_directory=None)
        with patch("scripts.collect_lpse_detail_evidence.build_cli_routing_binding") as builder:
            self.assertIsNone(routing_binding_from_args(args))
        builder.assert_not_called()

    def test_partial_routing_arguments_fail_closed(self):
        for args in (
            argparse.Namespace(routing_kldi_id="D294", sirup_run_directory=None),
            argparse.Namespace(routing_kldi_id=None, sirup_run_directory=Path("validated-run")),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                routing_binding_from_args(args)


class RawRootIsolationTests(unittest.TestCase):
    def test_parse_args_raw_root_default_and_custom(self) -> None:
        from scripts.collect_lpse_detail_evidence import RAW_DIR, parse_args

        with patch("sys.argv", ["collect_lpse_detail_evidence.py"]):
            args = parse_args()

        self.assertEqual(RAW_DIR, args.raw_root)

        custom = Path("data/evidence/lpse/bounded/test-task")

        with patch(
            "sys.argv",
            [
                "collect_lpse_detail_evidence.py",
                "--raw-root",
                str(custom),
            ],
        ):
            args = parse_args()

        self.assertEqual(custom, args.raw_root)



    def test_collect_normalizes_relative_raw_root_against_repository_root(self) -> None:
        from scripts.collect_lpse_detail_evidence import ROOT, collect

        relative = Path("data/evidence/lpse/bounded/test-relative")

        args = SimpleNamespace(
            raw_root=relative,
            national_sample=None,
            limit_lpse=0,
            limit_packages=0,
            year=2026,
            sleep=0,
            timeout=30,
        )

        with (
            patch("scripts.collect_lpse_detail_evidence.pd.read_csv", return_value=pd.DataFrame()),
            patch("scripts.collect_lpse_detail_evidence.select_registry_rows", return_value=[]),
            patch("scripts.collect_lpse_detail_evidence.make_opener", return_value=object()),
        ):
            collect(args)

        self.assertTrue(args.raw_root.is_absolute())
        self.assertEqual(ROOT / relative, args.raw_root)

    def test_collect_preserves_absolute_raw_root(self) -> None:
        from scripts.collect_lpse_detail_evidence import ROOT, collect

        absolute = ROOT / "data" / "evidence" / "lpse" / "bounded" / "test-absolute"

        args = SimpleNamespace(
            raw_root=absolute,
            national_sample=None,
            limit_lpse=0,
            limit_packages=0,
            year=2026,
            sleep=0,
            timeout=30,
        )

        with (
            patch("scripts.collect_lpse_detail_evidence.pd.read_csv", return_value=pd.DataFrame()),
            patch("scripts.collect_lpse_detail_evidence.select_registry_rows", return_value=[]),
            patch("scripts.collect_lpse_detail_evidence.make_opener", return_value=object()),
        ):
            collect(args)

        self.assertEqual(absolute, args.raw_root)



if __name__ == "__main__":
    unittest.main()
