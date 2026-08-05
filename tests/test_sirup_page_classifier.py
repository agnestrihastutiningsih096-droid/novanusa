import copy
import unittest

from scripts.sirup_page_classifier import classify_page_rows


class SirupPageClassifierTests(unittest.TestCase):
    required = {"id", "name", "year"}

    def classify(self, rows, records_filtered=50, expected_count=None):
        payload = {"data": rows, "recordsFiltered": records_filtered}
        count = len(rows) if expected_count is None else expected_count
        return classify_page_rows(payload, count, self.required)

    def test_all_valid_page_schema_order_and_accounting(self):
        rows = [
            {"id": 2, "name": "second", "year": 2026},
            {"id": 1, "name": "first", "year": 2026},
        ]
        result = self.classify(rows, records_filtered=123)
        self.assertEqual(result, {
            "records_filtered": 123,
            "source_row_count": 2,
            "valid_rows": rows,
            "invalid_rows": [],
            "valid_row_count": 2,
            "invalid_row_count": 0,
        })
        self.assertIs(result["valid_rows"][0], rows[0])
        self.assertEqual(result["source_row_count"],
                         result["valid_row_count"] + result["invalid_row_count"])

    def test_missing_required_fields_are_sorted(self):
        row = {"id": 7}
        invalid = self.classify([row])["invalid_rows"][0]
        self.assertEqual(invalid["missing_fields"], ["name", "year"])
        self.assertEqual(invalid["invalid_fields"], [])
        self.assertEqual(invalid["package_id"], 7)
        self.assertEqual(
            invalid["validation_error"],
            "row 0 is missing fields: name, year")

    def test_null_id(self):
        invalid = self.classify(
            [{"id": None, "name": "x", "year": 2026}])["invalid_rows"][0]
        self.assertEqual(invalid["missing_fields"], [])
        self.assertEqual(invalid["invalid_fields"], ["id"])
        self.assertIsNone(invalid["package_id"])
        self.assertEqual(invalid["validation_error"], "row 0 has a null id")

    def test_non_object_row(self):
        invalid = self.classify(["raw"])["invalid_rows"][0]
        self.assertEqual(invalid, {
            "row_index": 0, "raw_row": "raw", "package_id": None,
            "missing_fields": [], "invalid_fields": ["row"],
            "validation_error": "row 0 is not an object",
        })

    def test_duplicate_marks_every_occurrence_and_removes_both(self):
        first = {"id": 4, "name": "a", "year": 2026}
        middle = {"id": 5, "name": "b", "year": 2026}
        last = {"id": 4, "name": "c", "year": 2026}
        result = self.classify([first, middle, last])
        self.assertEqual(result["valid_rows"], [middle])
        self.assertEqual([item["row_index"] for item in result["invalid_rows"]],
                         [0, 2])
        for index, invalid in zip((0, 2), result["invalid_rows"]):
            self.assertEqual(invalid["invalid_fields"], ["id"])
            self.assertEqual(invalid["validation_error"],
                             f"row {index} has a duplicate id: 4")
        self.assertNotIn(first, result["valid_rows"])
        self.assertNotIn(last, result["valid_rows"])

    def test_multiple_independent_invalid_rows_preserve_source_order(self):
        rows = [
            {"id": 1, "name": "valid", "year": 2026},
            {"id": 2, "year": 2026},
            None,
            {"id": 3, "name": "valid too", "year": 2026},
            {"id": None, "name": "null", "year": 2026},
        ]
        result = self.classify(rows)
        self.assertEqual(result["valid_rows"], [rows[0], rows[3]])
        self.assertEqual([item["row_index"] for item in result["invalid_rows"]],
                         [1, 2, 4])
        self.assertEqual(result["source_row_count"],
                         result["valid_row_count"] + result["invalid_row_count"])

    def test_multiple_defects_are_all_reported_deterministically(self):
        rows = [
            {"id": 9, "year": 2026},
            {"id": 9, "name": "duplicate", "year": 2026},
        ]
        invalid = self.classify(rows)["invalid_rows"][0]
        self.assertEqual(invalid["missing_fields"], ["name"])
        self.assertEqual(invalid["invalid_fields"], ["id"])
        self.assertEqual(
            invalid["validation_error"],
            "row 0 is missing fields: name; row 0 has a duplicate id: 9")

    def test_payload_nested_rows_and_required_fields_are_not_modified(self):
        required = ["year", "id", "name"]
        payload = {"data": [{"id": 1, "name": "x", "year": 2026,
                             "nested": {"values": [1, 2]}}],
                   "recordsFiltered": 1}
        before = copy.deepcopy(payload)
        nested = payload["data"][0]["nested"]
        classify_page_rows(payload, 1, required)
        self.assertEqual(payload, before)
        self.assertEqual(required, ["year", "id", "name"])
        self.assertIs(payload["data"][0]["nested"], nested)

    def test_page_level_structural_errors(self):
        cases = [
            ("root", [], 0, RuntimeError),
            ("data missing", {"recordsFiltered": 0}, 0, RuntimeError),
            ("data type", {"data": {}, "recordsFiltered": 0}, 0, RuntimeError),
            ("row count", {"data": [], "recordsFiltered": 0}, 1, RuntimeError),
            ("records missing", {"data": []}, 0, RuntimeError),
            ("records type", {"data": [], "recordsFiltered": "0"}, 0,
             RuntimeError),
        ]
        for name, payload, count, error in cases:
            with self.subTest(name=name), self.assertRaises(error):
                classify_page_rows(payload, count, self.required)

    def test_invalid_expected_count_rejected(self):
        for value in (-1, 1.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                classify_page_rows({"data": [], "recordsFiltered": 0},
                                   value, self.required)

    def test_invalid_required_fields_rejected(self):
        for value in ([], set(), "id", ["id", ""], [1]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                classify_page_rows({"data": [], "recordsFiltered": 0}, 0, value)

    def test_empty_page(self):
        result = classify_page_rows(
            {"data": [], "recordsFiltered": 0}, 0, {"id"})
        self.assertEqual(result["source_row_count"], 0)
        self.assertEqual(result["valid_rows"], [])
        self.assertEqual(result["invalid_rows"], [])
        self.assertEqual(result["valid_row_count"] + result["invalid_row_count"], 0)


if __name__ == "__main__":
    unittest.main()
