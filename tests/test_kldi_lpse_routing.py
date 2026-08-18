from __future__ import annotations

import dataclasses
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import kldi_lpse_routing as routing  # noqa: E402
from current_institution_identity_provider import (  # noqa: E402
    CurrentInstitutionIdentityProvider,
    InstitutionIdentityProviderError,
)
from current_procurement_contracts import (  # noqa: E402
    ContractError,
    LinkEvidenceKind,
    LinkState,
    ProcurementRealizationLink,
    verify_realization_link,
)


class KldiLpseRoutingTests(unittest.TestCase):
    def sirup(self, **changes):
        values = dict(
            canonical_kldi_id="D294", source_kldi_name="Kab. Halmahera Tengah",
            acquisition_run_id="20260817T043259Z-2026-100rows",
            receipt_chain_reference="receipt-chain:20260817T043259Z-2026-100rows",
            receipt_chain_hash="60ccad916491f8100fe9a14340f0cd4609ca54f0e4f647ad97207ef73ac6b840",
            source_version="sirup-authenticated-2026-08-17", province="Maluku Utara",
            government_level="Kabupaten",
        )
        values.update(changes)
        return routing.SirupRoutingEvidence(**values)

    def registry(self, **changes):
        values = dict(
            lpse_name="LPSE Kabupaten Halmahera Tengah",
            official_lpse_url="https://spse.inaproc.id/haltengkab",
            registry_artifact_id="official-lpse-registry-2026-08-17",
            registry_artifact_hash="registry-sha256-example",
            registry_version="2026-08-17", province="Maluku Utara",
            government_level="Pemerintah Kabupaten",
        )
        values.update(changes)
        return routing.LpseRegistryEvidence(**values)

    def build(self, sirup=None, rows=None, **kwargs):
        return routing.build_kldi_lpse_routing_binding(
            sirup or self.sirup(), [self.registry()] if rows is None else rows, **kwargs
        )

    def test_d294_routes_to_exact_official_endpoint(self):
        binding = self.build()
        self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_ACTIVE, binding.status)
        self.assertEqual("https://spse.inaproc.id/haltengkab", routing.lookup_lpse_route(binding))
        self.assertEqual("Kabupaten Halmahera Tengah", binding.normalized_organization_name)
        self.assertEqual("ROUTING_ONLY", binding.authority_scope)

    def test_repeated_execution_is_deterministic(self):
        self.assertEqual(self.build(), self.build())
        self.assertEqual(self.build().binding_digest, self.build().binding_digest)

    def test_multiple_candidates_are_ambiguous_and_not_routable(self):
        binding = self.build(rows=[self.registry(), self.registry(official_lpse_url="https://example.invalid/other")])
        self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_AMBIGUOUS, binding.status)
        self.assertIsNone(routing.lookup_lpse_route(binding))

    def test_zero_candidates_are_rejected(self):
        binding = self.build(rows=[self.registry(lpse_name="LPSE Kabupaten Lain")])
        self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_REJECTED, binding.status)
        self.assertIsNone(routing.lookup_lpse_route(binding))

    def test_province_and_government_level_conflicts_reject(self):
        for change in ({"province": "Papua"}, {"government_level": "Pemerintah Kota"}):
            with self.subTest(change=change):
                binding = self.build(rows=[self.registry(**change)])
                self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_REJECTED, binding.status)
                self.assertIsNone(routing.lookup_lpse_route(binding))

    def test_missing_sirup_or_registry_provenance_rejects(self):
        cases = (
            self.build(sirup=self.sirup(acquisition_run_id="")),
            self.build(rows=[self.registry(registry_artifact_hash="")]),
        )
        for binding in cases:
            self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_REJECTED, binding.status)

    def test_rule_and_source_versions_are_bound_and_changes_make_stale(self):
        binding = self.build(normalization_rule_version="strict-v7")
        self.assertNotEqual(binding.binding_digest, self.build().binding_digest)
        for kwargs in (
            {"normalization_rule_version": "strict-v8"},
            {"sirup_source_version": "new-sirup"},
            {"registry_version": "new-registry"},
        ):
            stale = routing.validate_routing_authority(binding, **kwargs)
            self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_STALE, stale.status)
            self.assertIsNone(routing.lookup_lpse_route(stale))

    def test_url_change_requires_a_distinct_authority_digest(self):
        original = self.build()
        changed = self.build(rows=[self.registry(official_lpse_url="https://spse.inaproc.id/haltengkab-v2")])
        self.assertNotEqual(original.binding_digest, changed.binding_digest)
        tampered = dataclasses.replace(original, official_lpse_url=changed.official_lpse_url)
        self.assertIsNone(routing.lookup_lpse_route(tampered))

    def test_contract_has_no_fuzzy_or_llm_path_and_uses_no_network(self):
        self.assertFalse(hasattr(routing, "similarity"))
        self.assertFalse(hasattr(routing, "SequenceMatcher"))
        with mock.patch.object(socket, "create_connection") as connect:
            self.build()
        connect.assert_not_called()

    def test_routing_binding_is_rejected_by_identity_and_realization_authorities(self):
        binding = self.build()
        with self.assertRaises(InstitutionIdentityProviderError):
            CurrentInstitutionIdentityProvider(object(), [binding], dataset_version="v1")
        with self.assertRaises((ContractError, TypeError, AttributeError)):
            verify_realization_link(binding)  # type: ignore[arg-type]
        with self.assertRaises((ContractError, AttributeError, TypeError)):
            ProcurementRealizationLink(
                "planned", "execution", LinkState.LINK_VERIFIED,
                LinkEvidenceKind.TITLE_CANDIDATE_ONLY, binding.binding_digest, object()
            )


if __name__ == "__main__":
    unittest.main()
