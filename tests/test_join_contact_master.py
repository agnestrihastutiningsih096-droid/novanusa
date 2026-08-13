from dataclasses import replace
import unittest

from scripts.join_contact_master import CanonicalContact, build_index, enrich_outreach_row, normalize


def contact(
    name: str = "Dinas Pendidikan",
    *,
    parent: str = "Pemerintah Kota A",
    region: str = "Jawa Barat",
    email: str = "contact@example.go.id",
    confidence: float = 0.5,
    completeness: float = 10.0,
    row: int = 1,
) -> CanonicalContact:
    display = f"{name} — {parent}" if parent else name
    return CanonicalContact(
        source_file="master.csv", source_type="contact_master", source_priority=1,
        source_confidence=confidence, source_row=row, institution_name=name,
        parent_organization=parent, work_unit=name, region=region,
        institution_display_name=display, contact_email=email,
        official_website="https://example.go.id", contact_phone="", contact_whatsapp="",
        contact_person="", contact_role="", contact_source_url="https://example.go.id/contact",
        contact_notes="", contact_source_type="contact_master",
        match_keys={
            "institution_display_name": normalize(display),
            "work_unit_parent": f"{name.lower()} || {parent.lower()}" if parent else "",
            "institution_region": f"{name.lower()} || {region.lower()}" if region else "",
            "institution_name": name.lower(),
        }, completeness_score=completeness,
    )


def target(**overrides: str) -> dict[str, str]:
    base = {
        "institution_name": "Dinas Pendidikan",
        "institution_display_name": "Dinas Pendidikan — Pemerintah Kota A",
        "parent_organization": "Pemerintah Kota A",
        "work_unit": "Dinas Pendidikan",
        "province_or_region": "Jawa Barat",
        "location_hint": "",
    }
    base.update(overrides)
    return base


def enrich(candidates: list[CanonicalContact], **overrides: str) -> dict[str, str]:
    return enrich_outreach_row(target(**overrides), build_index(candidates))[0]


def test_unique_exact_display_resolves_when_authority_is_consistent() -> None:
    result = enrich([contact()])
    assert result["contact_match_type"] == "exact_display_name"
    assert result["contact_status"] == "CONTACT_FOUND"


def test_exact_display_with_explicit_authority_conflict_fails_closed() -> None:
    candidate = contact(region="Jawa Timur")
    result = enrich([candidate])
    assert result["contact_status"] == "CONTACT_MISSING"


def test_unique_institution_name_region_resolves() -> None:
    result = enrich([contact()], institution_display_name="", work_unit="", parent_organization="")
    assert result["contact_match_type"] == "institution_name_region"
    assert result["contact_status"] == "CONTACT_FOUND"


def test_normalized_name_only_unique_candidate_is_discovery_only() -> None:
    result = enrich([contact(region="")], institution_display_name="", work_unit="", parent_organization="", province_or_region="")
    assert result["contact_match_type"] == "unmatched"
    assert result["contact_status"] == "CONTACT_MISSING"


def test_normalized_name_collision_cannot_select_a_winner() -> None:
    candidates = [contact(parent="Kota A", region="Barat"), contact(parent="Kota B", region="Timur")]
    result = enrich(candidates, institution_display_name="", work_unit="", parent_organization="", province_or_region="")
    assert result["contact_status"] == "CONTACT_MISSING"


def test_normalized_name_cross_region_mismatch_fails_closed() -> None:
    result = enrich([contact(region="Jawa Timur")], institution_display_name="", work_unit="", parent_organization="")
    assert result["contact_status"] == "CONTACT_MISSING"


def test_collision_resolution_is_independent_of_source_row_order() -> None:
    candidates = [contact(parent="Kota A", region="Barat"), contact(parent="Kota B", region="Timur")]
    kwargs = dict(institution_display_name="", work_unit="", parent_organization="", province_or_region="")
    assert enrich(candidates, **kwargs)["contact_status"] == "CONTACT_MISSING"
    assert enrich(list(reversed(candidates)), **kwargs)["contact_status"] == "CONTACT_MISSING"


def test_collision_resolution_ignores_completeness_score() -> None:
    candidates = [contact(parent="Kota A", region="Barat", completeness=1), contact(parent="Kota B", region="Timur", completeness=999)]
    result = enrich(candidates, institution_display_name="", work_unit="", parent_organization="", province_or_region="")
    assert result["contact_status"] == "CONTACT_MISSING"


def test_collision_resolution_ignores_source_confidence() -> None:
    candidates = [contact(parent="Kota A", region="Barat", confidence=0), contact(parent="Kota B", region="Timur", confidence=1)]
    result = enrich(candidates, institution_display_name="", work_unit="", parent_organization="", province_or_region="")
    assert result["contact_status"] == "CONTACT_MISSING"


def test_safe_duplicate_evidence_for_one_authority_is_deterministic() -> None:
    weaker = contact(email="weak@example.go.id", completeness=1, row=1)
    stronger = replace(weaker, contact_email="strong@example.go.id", completeness_score=2, source_row=2)
    first = enrich([weaker, stronger])
    second = enrich([stronger, weaker])
    assert first["contact_email"] == second["contact_email"] == "strong@example.go.id"


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    del loader, tests, pattern
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value, description=name))
    return suite
