from scripts.demand_taxonomy_v1_classifier import (
    DEMAND_FAMILIES,
    SEMANTIC_STATES,
    classify_demand,
)


def _assert_case(title, state, families):
    result = classify_demand(title)
    assert result.semantic_state == state
    assert result.demand_families == tuple(families)
    assert all(term.family in result.demand_families for term in result.matched_terms)
    assert result.rule_ids[-1] == f"STATE.{state}"


ADVERSARIAL = (
    ("Pengadaan Pemeliharaan Printer", "MAINTENANCE_CALIBRATION", ("PRINTING_HARDWARE",)),
    ("Sewa Laptop", "RENTAL_SUBSCRIPTION_LICENSE", ("COMPUTING",)),
    ("Laptop", "PRODUCT_ONLY_UNCONTRADICTED", ("COMPUTING",)),
    ("Tinta Printer", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Patient Monitor", "PRODUCT_ONLY_UNCONTRADICTED", ("MEDICAL_MONITOR",)),
    ("Iklan Media Televisi", "MEDIA_SERVICE", ("DISPLAY",)),
    ("Lisensi Video Conference", "RENTAL_SUBSCRIPTION_LICENSE", ("VIDEO_CONFERENCE_SOFTWARE_LICENSE",)),
    ("Fiber Optic Laryngoscope", "NO_GOVERNED_DEMAND_MATCH", ()),
    ("Pemotretan Drone", "SERVICE_CONTEXT", ("DRONE",)),
    ("Kalibrasi Centrifuge", "MAINTENANCE_CALIBRATION", ("MEDICAL_LAB",)),
    ("Pengadaan Pemeliharaan AC Split", "MAINTENANCE_CALIBRATION", ("AIR_CONDITIONING",)),
    ("Pengadaan Sewa Laptop", "RENTAL_SUBSCRIPTION_LICENSE", ("COMPUTING",)),
)


def test_adversarial_a_l():
    for case in ADVERSARIAL:
        _assert_case(*case)


COLLISIONS = (
    ("Lisensi Remote Desktop", "RENTAL_SUBSCRIPTION_LICENSE", ()),
    ("Balai Monitor SFR Kelas II", "NO_GOVERNED_DEMAND_MATCH", ()),
    ("Pengadaan PC Monitor 24 Inch", "PURCHASE_EXPLICIT", ("DISPLAY",)),
    ("Pengadaan Patient Monitor", "PURCHASE_EXPLICIT", ("MEDICAL_MONITOR",)),
    ("Langganan Internet Fiber Optik", "RENTAL_SUBSCRIPTION_LICENSE", ()),
    ("Pengadaan Kabel Fiber Optik", "PURCHASE_EXPLICIT", ("NETWORK_MATERIAL",)),
    ("Centrifuge Tube", "PARTS_CONSUMABLE", ()),
    ("Pengadaan Refrigerated Centrifuge", "PURCHASE_EXPLICIT", ("MEDICAL_LAB",)),
    ("Metric Aerial Camera and Lidar Survey", "NO_GOVERNED_DEMAND_MATCH", ()),
    ("Pengadaan Camera Mirrorless", "PURCHASE_EXPLICIT", ("CAMERA",)),
)


def test_collision_x1_x10():
    for case in COLLISIONS:
        _assert_case(*case)


PRINTING = (
    ("Tinta Printer", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Refill Printer Laserjet HP 35 A", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Toner untuk printer Dit. Prestasi", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Pengadaan Perlengkapan Printer berupa toner", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Kebutuhan Printer (Tinta dan Pita Printer)", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Refill Ink Printer dan Laser Pointer", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Tinta Epson EcoTank 003 Original Yellow Refil Ink Printer L1110 L3110 L3150 L5190", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("BLUD - Penyediaan Refill Toner Printer Laserjet", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Belanja Refil Toner / Cartridge Printer Laserjet", "PARTS_CONSUMABLE", ("PRINTING_CONSUMABLES",)),
    ("Printer", "PRODUCT_ONLY_UNCONTRADICTED", ("PRINTING_HARDWARE",)),
    ("Pengadaan Printer", "PURCHASE_EXPLICIT", ("PRINTING_HARDWARE",)),
    ("Printer Laserjet", "PRODUCT_ONLY_UNCONTRADICTED", ("PRINTING_HARDWARE",)),
    ("Belanja Modal Printer Inkjet", "PURCHASE_EXPLICIT", ("PRINTING_HARDWARE",)),
    ("Pengadaan Printer dan Tinta Printer", "PURCHASE_EXPLICIT", ("PRINTING_CONSUMABLES", "PRINTING_HARDWARE")),
    ("Printer LaserJet dan Toner LaserJet", "PRODUCT_ONLY_UNCONTRADICTED", ("PRINTING_CONSUMABLES", "PRINTING_HARDWARE")),
    ("Pekerjaan Pengadaan Laptop, Printer, Tinta Printer dan Modem", "PURCHASE_EXPLICIT", ("COMPUTING", "PRINTING_CONSUMABLES", "PRINTING_HARDWARE")),
    ("Refill Ink Epson dan Printer Inkjet Multifungsi, up to A4", "PRODUCT_ONLY_UNCONTRADICTED", ("PRINTING_CONSUMABLES", "PRINTING_HARDWARE")),
)


def test_printing_v678():
    for case in PRINTING:
        _assert_case(*case)


def test_frozen_bindings_and_enumerations():
    result = classify_demand("")
    assert result.taxonomy_version == "DEMAND_TAXONOMY_V1_CANDIDATE_FINAL_R2_2_2026-08-14"
    assert result.taxonomy_sha256 == "3864ef756fc96aa5e0454335f0ac38154d3a3417a6e5300b781ed550f657ffe0"
    assert result.printing_resolver_version == "V6.7.8"
    assert len(DEMAND_FAMILIES) == 20
    assert len(SEMANTIC_STATES) == 11


def test_unverified_expansion_is_not_authority():
    for title in ("tower server", "blade server", "surveillance camera", "conference speaker", "speaker conference", "web conference", "firewall appliance", "external hard drive", "voltage stabilizer", "kursi dental", "timbangan medis"):
        _assert_case(title, "NO_GOVERNED_DEMAND_MATCH", ())


def test_normalization_boundaries_and_jenis_is_not_family_authority():
    assert classify_demand("  PENGADAAN—LAPTOP\t").demand_families == ("COMPUTING",)
    assert classify_demand("notebooking").demand_families == ()
    assert classify_demand("unknown", "Pengadaan Laptop").demand_families == ()


def test_deterministic_replay():
    corpus = ADVERSARIAL + COLLISIONS + PRINTING
    first = tuple(classify_demand(title) for title, _, _ in corpus)
    for _ in range(100):
        assert tuple(classify_demand(title) for title, _, _ in corpus) == first
