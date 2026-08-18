import unittest
from dataclasses import replace
from unittest.mock import patch

import pandas as pd

from scripts.collect_lpse_detail_evidence import (
    OUTPUT_COLUMNS,
    extract_tables,
    parse_detail_fields,
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


if __name__ == "__main__":
    unittest.main()
