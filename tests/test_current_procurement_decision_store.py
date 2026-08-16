import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from current_procurement_decision_store import (  # noqa: E402
    DecisionStoreError,
    ProcurementDecisionStore,
    RECORD_SCHEMA,
    RECORD_VERSION,
    STORE_SCHEMA,
    STORE_VERSION,
)


def record(decision_id="decision-1", result="VERIFIED", evidence=None):
    return {
        "schema": RECORD_SCHEMA,
        "version": RECORD_VERSION,
        "decision_id": decision_id,
        "kind": "IDENTITY",
        "result": result,
        "subject": "planned-1",
        "provenance": ["CURRENT_SIRUP", "acq-1", "receipt-1"],
        "evidence_references": evidence or ["row-1"],
        "timestamp": "2026-08-16T00:00:00+00:00",
        "bindings": {"id_satker": "338553"},
    }


class DecisionStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "procurement-decisions.json"

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_is_empty_and_append_survives_recreation(self):
        self.assertEqual((), ProcurementDecisionStore(self.path).read())
        ProcurementDecisionStore(self.path).append(record())
        recreated = ProcurementDecisionStore(self.path)
        self.assertTrue(recreated.contains_exact(record()))
        self.assertEqual(1, len(recreated.read()))

    def test_append_preserves_history_and_uses_store_envelope(self):
        store = ProcurementDecisionStore(self.path)
        store.append(record())
        second = record("decision-2")
        second["kind"] = "EXECUTION"
        second["subject"] = "execution-1"
        second["bindings"] = {"source_package_id": "spse-1"}
        store.append(second)
        state = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((STORE_SCHEMA, STORE_VERSION), (state["schema"], state["version"]))
        self.assertEqual(["decision-1", "decision-2"], [item["decision_id"] for item in state["decisions"]])
        self.assertFalse(any(self.path.parent.glob(f".{self.path.name}.*.tmp")))

    def test_repeated_equivalent_authority_is_append_only(self):
        store = ProcurementDecisionStore(self.path)
        store.append(record())
        equivalent = record("decision-2")
        equivalent["timestamp"] = "2026-08-16T00:01:00+00:00"
        store.append(equivalent)
        self.assertEqual(2, len(ProcurementDecisionStore(self.path).read()))

    def test_corrupt_and_incomplete_state_fail_closed(self):
        for content in ("not json", json.dumps({"schema": STORE_SCHEMA, "version": STORE_VERSION})):
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                with self.assertRaises(DecisionStoreError):
                    ProcurementDecisionStore(self.path).read()

    def test_contradictory_authoritative_records_fail_closed(self):
        first = record()
        contradiction = record("decision-2", evidence=["different-row"])
        state = {"schema": STORE_SCHEMA, "version": STORE_VERSION, "decisions": [first, contradiction]}
        self.path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(DecisionStoreError):
            ProcurementDecisionStore(self.path).read()

    def test_exact_lookup_rejects_wrong_kind_and_binding(self):
        store = ProcurementDecisionStore(self.path)
        expected = record()
        store.append(expected)
        wrong_kind = {**expected, "kind": "EXECUTION"}
        wrong_binding = {**expected, "bindings": {"id_satker": "other"}}
        self.assertFalse(store.contains_exact(wrong_kind))
        self.assertFalse(store.contains_exact(wrong_binding))


if __name__ == "__main__":
    unittest.main()
