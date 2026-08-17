import unittest

from scripts.collect_lpse_detail_evidence import OUTPUT_COLUMNS, extract_tables, parse_detail_fields


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


if __name__ == "__main__":
    unittest.main()
