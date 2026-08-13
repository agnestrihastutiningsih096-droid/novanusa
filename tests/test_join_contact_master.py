from dataclasses import replace
import csv
from pathlib import Path
import tempfile
import unittest

from scripts.join_contact_master import (
    CanonicalContact, KNOWN_SOURCE_SCHEMAS, build_index, canonicalize_row,
    determine_contact_scope, enrich_outreach_row, is_direct_outreach_eligible,
    is_valid_provenance_url, load_contact_rows, normalize, select_equivalent_sources,
)


def contact(
    name: str = "Dinas Pendidikan",
    *,
    parent: str = "Pemerintah Kota A",
    region: str = "Jawa Barat",
    email: str = "contact@example.go.id",
    confidence: float = 0.5,
    completeness: float = 10.0,
    row: int = 1,
    source_file: str = "master.csv",
    endpoint_organization: str = "",
    endpoint_binding_explicit: bool = False,
) -> CanonicalContact:
    display = f"{name} — {parent}" if parent else name
    return CanonicalContact(
        source_file=source_file, source_type="contact_master", source_priority=1,
        source_confidence=confidence, source_row=row, institution_name=name,
        parent_organization=parent, work_unit=name, region=region,
        institution_display_name=display, contact_email=email,
        official_website="https://example.go.id", contact_phone="", contact_whatsapp="",
        contact_person="", contact_role="", contact_source_url="https://example.go.id/contact",
        contact_notes="", contact_source_type="contact_master",
        endpoint_organization=endpoint_organization,
        endpoint_binding_explicit=endpoint_binding_explicit,
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


def test_void_authority_cannot_establish_contact() -> None:
    result = enrich([contact(parent="", region="")], parent_organization="", province_or_region="")
    assert result["contact_status"] == "CONTACT_MISSING"


def test_parent_only_exact_display_with_matching_explicit_parent_resolves() -> None:
    result = enrich([contact(region="")], province_or_region="")
    assert result["contact_match_type"] == "exact_display_name"
    assert result["contact_status"] == "CONTACT_FOUND"


def test_region_only_strong_match_with_matching_explicit_region_resolves() -> None:
    result = enrich(
        [contact(parent="", region="Jawa Barat")],
        institution_display_name="Dinas Pendidikan", parent_organization="",
    )
    assert result["contact_match_type"] == "exact_display_name"
    assert result["contact_status"] == "CONTACT_FOUND"


def test_region_only_conflict_fails_closed() -> None:
    result = enrich(
        [contact(parent="", region="Jawa Timur")],
        institution_display_name="Dinas Pendidikan", parent_organization="",
    )
    assert result["contact_status"] == "CONTACT_MISSING"


def test_explicit_exact_endpoint_binding_is_direct_institution() -> None:
    candidate = contact(
        endpoint_organization="Dinas Pendidikan", endpoint_binding_explicit=True,
    )
    assert enrich([candidate])["contact_scope"] == "DIRECT_INSTITUTION"


def test_verified_cache_parent_endpoint_for_exact_child_is_hierarchy_official() -> None:
    candidate = contact(
        name="Cabang Dinas Pendidikan Wilayah Mojokerto",
        parent="Provinsi Jawa Timur", region="",
        source_file="verified_cache_contacts_1640.csv",
        endpoint_organization="Dinas Pendidikan", endpoint_binding_explicit=True,
    )
    result = enrich(
        [candidate], institution_name="Cabang Dinas Pendidikan Wilayah Mojokerto",
        institution_display_name="Cabang Dinas Pendidikan Wilayah Mojokerto — Provinsi Jawa Timur",
        work_unit="Cabang Dinas Pendidikan Wilayah Mojokerto",
        parent_organization="Provinsi Jawa Timur", province_or_region="",
    )
    assert result["contact_status"] == "CONTACT_FOUND"
    assert result["contact_scope"] == "HIERARCHY_OFFICIAL"


def test_verified_cache_parent_endpoint_reused_across_siblings_is_hierarchy() -> None:
    for child in ("Cabang Dinas Pendidikan Wilayah Mojokerto", "Cabang Dinas Pendidikan Wilayah Sampang"):
        candidate = contact(
            name=child, parent="Provinsi Jawa Timur", region="",
            source_file="verified_cache_contacts_1640.csv",
            endpoint_organization="Dinas Pendidikan", endpoint_binding_explicit=True,
        )
        result = enrich(
            [candidate], institution_name=child,
            institution_display_name=f"{child} — Provinsi Jawa Timur", work_unit=child,
            parent_organization="Provinsi Jawa Timur", province_or_region="",
        )
        assert result["contact_scope"] == "HIERARCHY_OFFICIAL"


def test_exact_identity_without_endpoint_scope_evidence_is_unresolved() -> None:
    assert enrich([contact(confidence=1.0)])["contact_scope"] == "UNRESOLVED"


def test_missing_and_unproven_review_scope_are_unresolved() -> None:
    assert enrich([])["contact_scope"] == "UNRESOLVED"
    review = replace(contact(), contact_source_url="")
    result = enrich([review])
    assert result["contact_status"] == "CONTACT_NEEDS_REVIEW"
    assert result["contact_scope"] == "UNRESOLVED"


def test_direct_outreach_eligibility_requires_found_and_direct_scope() -> None:
    assert is_direct_outreach_eligible("CONTACT_FOUND", "DIRECT_INSTITUTION")
    assert not is_direct_outreach_eligible("CONTACT_FOUND", "HIERARCHY_OFFICIAL")
    assert not is_direct_outreach_eligible("CONTACT_FOUND", "UNRESOLVED")
    assert not is_direct_outreach_eligible("CONTACT_NEEDS_REVIEW", "DIRECT_INSTITUTION")
    assert not is_direct_outreach_eligible("CONTACT_NEEDS_REVIEW", "UNRESOLVED")


def test_confidence_verified_level_and_shared_email_do_not_create_direct_scope() -> None:
    first = contact(email="shared@example.go.id", confidence=1.0)
    second = replace(first, source_row=2)
    assert determine_contact_scope("CONTACT_FOUND", first, "Dinas Pendidikan") == "UNRESOLVED"
    assert enrich([first, second])["contact_scope"] == "UNRESOLVED"


def test_row_identity_does_not_create_endpoint_binding_for_unproven_sources() -> None:
    fixtures = [
        (Path("institutions_enriched_contacts.csv"), {
            "name": "Unit", "email": "unit@example.go.id",
            "source_url": "https://example.go.id/evidence",
        }),
        (Path("tierA_contact_enriched_2026.csv"), {
            "institution_name": "Unit", "kldi": "Parent", "province": "Region",
            "research_email": "unit@example.go.id",
            "research_source_url": "https://example.go.id/evidence",
        }),
        (Path("contact-qwen-master-clean.csv"), {
            "institution": "Unit", "kldi": "Parent", "email": "unit@example.go.id",
            "source_url": "https://example.go.id/evidence",
        }),
    ]
    for path, row in fixtures:
        candidate = canonicalize_row(path, row, 1)
        assert not candidate.endpoint_binding_explicit
        assert determine_contact_scope("CONTACT_FOUND", candidate, "Unit") == "UNRESOLVED"


def test_provenance_url_validation_is_syntax_only_and_fail_closed() -> None:
    assert is_valid_provenance_url("http://example.go.id/evidence")
    assert is_valid_provenance_url("https://example.go.id/evidence")
    for invalid in (
        "", "0.80", "0.90", "medium", "high", "arbitrary text",
        "https:///missing-host", "ftp://example.go.id/evidence",
    ):
        assert not is_valid_provenance_url(invalid)


def test_email_provenance_status_and_authoritative_output_are_fail_closed() -> None:
    found = enrich([contact()])
    assert found["contact_status"] == "CONTACT_FOUND"
    assert found["contact_source_url"] == "https://example.go.id/contact"

    for invalid in ("", "0.90", "high", "ftp://example.go.id/evidence"):
        result = enrich([replace(contact(), contact_source_url=invalid)])
        assert result["contact_status"] == "CONTACT_NEEDS_REVIEW"
        assert result["contact_source_url"] == ""


def test_contact_status_vocabulary_is_canonical() -> None:
    statuses = {
        enrich([contact()])["contact_status"],
        enrich([replace(contact(), contact_source_url="")])["contact_status"],
        enrich([])["contact_status"],
    }
    assert statuses == {"CONTACT_FOUND", "CONTACT_NEEDS_REVIEW", "CONTACT_MISSING"}


def test_valid_provenance_alone_does_not_grant_endpoint_authority_or_outreach() -> None:
    candidate = contact(endpoint_binding_explicit=False)
    result = enrich([candidate])
    assert result["contact_status"] == "CONTACT_FOUND"
    assert result["contact_scope"] == "UNRESOLVED"
    assert not is_direct_outreach_eligible(result["contact_status"], result["contact_scope"])


def write_csv(path: Path, fieldnames: list[str], row: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def test_registry_covers_all_known_source_filenames() -> None:
    assert set(KNOWN_SOURCE_SCHEMAS) == {
        "institutions_enriched_contacts.csv", "contact-qwen-master-clean.csv",
        "tierA_contact_enriched_v2_2026.csv", "tierA_contact_enriched_2026.csv",
        "verified_cache_contacts_1640.csv",
    }


def test_known_source_schema_accepts_optional_contact_values_missing() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "contact-qwen-master-clean.csv"
        headers = sorted(KNOWN_SOURCE_SCHEMAS[path.name].required)
        row = {header: "" for header in headers}
        row.update({"institution": "Unit", "kldi": "Parent"})
        write_csv(path, headers, row)
        loaded = load_contact_rows(path)
        assert len(loaded) == 1
        assert loaded[0].contact_email == ""


def test_known_source_missing_required_column_rejects_whole_file() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "contact-qwen-master-clean.csv"
        headers = sorted(KNOWN_SOURCE_SCHEMAS[path.name].required - {"institution"})
        write_csv(path, headers, {header: "" for header in headers})
        try:
            load_contact_rows(path)
        except ValueError as exc:
            assert str(exc) == (
                "unsupported schema for contact-qwen-master-clean.csv; "
                "missing required columns: institution"
            )
        else:
            raise AssertionError("malformed known source was accepted")


def test_unknown_source_filename_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "unknown.csv"
        write_csv(path, ["institution"], {"institution": "Unit"})
        try:
            load_contact_rows(path)
        except ValueError as exc:
            assert "unknown contact source filename" in str(exc)
        else:
            raise AssertionError("unknown source was accepted")


def test_verified_cache_uses_kldi_as_parent_only_and_not_typology_as_region() -> None:
    candidate = canonicalize_row(
        Path("verified_cache_contacts_1640.csv"),
        {"institution_name": "Unit", "cache_kldi": "Parent",
         "institution_type": "Government Agency"}, 1,
    )
    assert candidate.parent_organization == "Parent"
    assert candidate.region == ""


def test_discovery_only_source_cannot_independently_create_contact_found() -> None:
    candidate = canonicalize_row(
        Path("institutions_enriched_contacts.csv"),
        {"name": "Dinas Pendidikan", "email": "x@example.go.id",
         "source_url": "https://example.go.id/contact"}, 1,
    )
    assert enrich([candidate])["contact_status"] == "CONTACT_MISSING"


def test_identical_duplicate_qwen_sources_are_deduplicated() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        first = base / "a" / "contact-qwen-master-clean.csv"
        second = base / "b" / "contact-qwen-master-clean.csv"
        first.parent.mkdir(); second.parent.mkdir()
        payload = b"institution,kldi,website,email,phone,whatsapp,source_url,confidence_score\n"
        first.write_bytes(payload); second.write_bytes(payload)
        assert select_equivalent_sources([first, second]) == [first]


def test_divergent_duplicate_qwen_sources_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        first = base / "a" / "contact-qwen-master-clean.csv"
        second = base / "b" / "contact-qwen-master-clean.csv"
        first.parent.mkdir(); second.parent.mkdir()
        first.write_bytes(b"one"); second.write_bytes(b"two")
        try:
            select_equivalent_sources([first, second])
        except ValueError as exc:
            assert "duplicate contact source conflict" in str(exc)
        else:
            raise AssertionError("divergent duplicate sources were accepted")


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    del loader, tests, pattern
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value, description=name))
    return suite
