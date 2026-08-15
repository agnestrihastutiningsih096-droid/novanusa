"""Deterministic implementation of the frozen NovaNusa Demand Taxonomy V1."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


TAXONOMY_VERSION = "DEMAND_TAXONOMY_V1_CANDIDATE_FINAL_R2_2_2026-08-14"
TAXONOMY_SHA256 = "3864ef756fc96aa5e0454335f0ac38154d3a3417a6e5300b781ed550f657ffe0"
PRINTING_RESOLVER_VERSION = "V6.7.8"

DEMAND_FAMILIES = (
    "AIR_CONDITIONING", "AUDIO_CONFERENCE", "CAMERA", "CCTV", "COMPUTING",
    "DISPLAY", "DRONE", "MEDICAL_LAB", "MEDICAL_MONITOR", "NETWORKING",
    "NETWORK_MATERIAL", "OFFICE_APPLIANCE", "OFFICE_FURNITURE", "POWER",
    "PRINTING_CONSUMABLES", "PRINTING_HARDWARE", "SERVER", "STORAGE",
    "VIDEO_CONFERENCE_HARDWARE", "VIDEO_CONFERENCE_SOFTWARE_LICENSE",
)

SEMANTIC_STATES = (
    "PURCHASE_EXPLICIT", "PRODUCT_ONLY_UNCONTRADICTED", "PARTS_CONSUMABLE",
    "MAINTENANCE_CALIBRATION", "RENTAL_SUBSCRIPTION_LICENSE",
    "INSTALLATION_CONTEXT", "SERVICE_CONTEXT", "MEDIA_SERVICE",
    "CONSULTING_OR_LABOR_SERVICE", "CONNECTIVITY_SERVICE",
    "NO_GOVERNED_DEMAND_MATCH",
)

_TAXONOMY = {
    "AIR_CONDITIONING": ("air conditioner", "air conditioning", "ac split", "pendingin ruangan"),
    "AUDIO_CONFERENCE": ("microphone", "mikrofon", "conference microphone", "audio conference"),
    "CAMERA": ("kamera", "camera digital", "digital camera", "camera mirrorless", "mirrorless camera", "camera dslr", "dslr camera"),
    "CCTV": ("cctv",),
    "COMPUTING": ("laptop", "notebook", "desktop pc", "komputer desktop", "pc desktop", "desktop computer", "all in one pc", "aio pc", "mini pc", "workstation"),
    "DISPLAY": ("digital signage", "interactive display", "interactive flat panel", "televisi", "monitor pc", "pc monitor", "led monitor", "lcd monitor", "monitor led", "monitor lcd", "monitor cctv", "display monitor", "pengadaan led display", "belanja led display", "peralatan led display"),
    "DRONE": ("drone", "dji", "gimbal"),
    "MEDICAL_LAB": ("dental chair", "mikroskop", "microscope", "centrifuge", "refrigerated centrifuge", "low speed centrifuge", "autoclave", "dermatoscope", "alat laboratorium", "laboratory equipment"),
    "MEDICAL_MONITOR": ("patient monitor", "pasien monitor", "invasive monitor", "blood pressure monitor", "nibp monitor"),
    "NETWORKING": ("router", "network switch", "access point", "wireless access point", "perangkat switch jaringan", "access switch jaringan"),
    "NETWORK_MATERIAL": ("kabel jaringan utp", "kabel lan", "kabel fiber optic", "kabel fiber optik", "jaringan fiber optic", "jaringan fiber optik", "peralatan fiber optic", "peralatan fiber optik", "backbone fiber optic", "backbone fiber optik", "gpon", "fusion splicer", "optical time domain reflectometer"),
    "OFFICE_APPLIANCE": ("dispenser", "coffee machine", "mesin kopi", "paper shredder", "penghancur kertas"),
    "OFFICE_FURNITURE": ("meja kantor", "kursi kantor", "meja kerja", "kursi kerja", "meja rapat", "kursi rapat", "lemari arsip", "filing cabinet"),
    "POWER": ("ups", "uninterruptible power supply", "stabilizer listrik"),
    "SERVER": ("server", "rack server"),
    "STORAGE": ("network attached storage", "nas storage", "storage server", "hard disk eksternal", "external ssd", "ssd eksternal"),
    "VIDEO_CONFERENCE_HARDWARE": ("conference camera", "video conference camera", "camera video conference", "perangkat video conference", "alat video conference", "sistem video conference"),
    "VIDEO_CONFERENCE_SOFTWARE_LICENSE": ("lisensi video conference", "aplikasi video conference", "langganan video conference", "video conferencing", "teleconference"),
}

_UNVERIFIED = ("tower server", "blade server", "surveillance camera", "conference speaker", "speaker conference", "web conference", "firewall appliance", "external hard drive", "voltage stabilizer", "kursi dental", "timbangan medis")

_CONTEXT = {
    "MAINTENANCE_CALIBRATION": ("pemeliharaan", "pemelihaaran", "maintenance", "perawatan", "perbaikan", "service", "servis", "harwat", "kalibrasi"),
    "RENTAL_SUBSCRIPTION_LICENSE": ("sewa", "rental", "langganan", "berlangganan", "subscription", "lisensi", "license"),
    "MEDIA_SERVICE": ("advertorial", "publikasi", "media televisi", "iklan", "reklame", "spot iklan", "tvc", "lipsus"),
    "CONSULTING_OR_LABOR_SERVICE": ("jasa konsultansi", "konsultan", "tenaga ahli", "programmer", "jasa tenaga"),
    "INSTALLATION_CONTEXT": ("instalasi", "pemasangan"),
    "SERVICE_CONTEXT": ("pemotretan",),
    "CONNECTIVITY_SERVICE": ("jasa internet", "layanan internet", "koneksi internet"),
    "PURCHASE_EXPLICIT": ("pengadaan", "pembelian", "belanja modal", "belanja barang", "belanja alat", "belanja peralatan"),
}


@dataclass(frozen=True, order=True)
class MatchedTerm:
    family: str
    term: str


@dataclass(frozen=True)
class DemandClassification:
    demand_families: tuple[str, ...]
    semantic_state: str
    matched_terms: tuple[MatchedTerm, ...]
    rule_ids: tuple[str, ...]
    taxonomy_version: str = TAXONOMY_VERSION
    taxonomy_sha256: str = TAXONOMY_SHA256
    printing_resolver_version: str = PRINTING_RESOLVER_VERSION


def _normalize(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _has(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


def _masked_unverified(text: str) -> str:
    for term in _UNVERIFIED:
        text = re.sub(r"(?<!\w)" + re.escape(term) + r"(?!\w)", " ", text)
    return " ".join(text.split())


def _printing_matches(text: str) -> tuple[bool, bool, tuple[str, ...], tuple[str, ...]]:
    consumable_patterns = (
        r"\btinta\s+printer\b", r"\bpita\s+printer\b",
        r"\b(?:refill|refil)\s+(?:ink\s+)?printer(?:\s+laserjet)?\b",
        r"\b(?:refill|refil)\s+(?:ink|toner)\b",
        r"\btoner(?:\s+untuk)?\s+printer\b", r"\btoner\s+laserjet\b",
        r"\bcartridge\s+printer\b", r"\bperlengkapan\s+printer\s+berupa\s+toner\b",
    )
    consumable_terms = []
    spans: list[tuple[int, int]] = []
    for pattern in consumable_patterns:
        for match in re.finditer(pattern, text):
            consumable_terms.append(match.group(0))
            spans.append(match.span())
    # In this accepted construction both printer tokens in the parenthetical
    # "Kebutuhan Printer (Tinta dan Pita Printer)" are referential.
    referential = re.search(r"\bkebutuhan\s+printer\s+tinta\s+dan\s+pita\s+printer\b", text)
    if referential:
        consumable_terms.append("kebutuhan printer tinta dan pita printer")
        spans.append(referential.span())
    residual_chars = list(text)
    for start, end in spans:
        residual_chars[start:end] = " " * (end - start)
    residual = "".join(residual_chars)
    consumable = bool(consumable_terms)
    hardware = _has(residual, "printer")
    rules = []
    if consumable:
        rules.append("PRINTING.CONSUMABLE_MASK")
    if hardware:
        rules.append("PRINTING.INDEPENDENT_HARDWARE")
    return consumable, hardware, tuple(sorted(set(consumable_terms))), tuple(rules)


def classify_demand(paket: str, jenis_pengadaan: str | None = None) -> DemandClassification:
    """Classify title evidence; ``jenis_pengadaan`` is corroborative, never sole family evidence."""
    title = _normalize(paket)
    corroboration = _normalize(jenis_pengadaan)
    governed_text = _masked_unverified(title)
    evidence: list[MatchedTerm] = []
    rules: list[str] = []

    for family in DEMAND_FAMILIES:
        if family.startswith("PRINTING_"):
            continue
        for term in _TAXONOMY.get(family, ()):
            if _has(governed_text, term):
                # A centrifuge tube is a part/consumable, not governed lab equipment.
                if family == "MEDICAL_LAB" and term == "centrifuge" and _has(title, "centrifuge tube"):
                    continue
                evidence.append(MatchedTerm(family, term))

    consumable, hardware, printing_terms, printing_rules = _printing_matches(title)
    if consumable:
        evidence.extend(MatchedTerm("PRINTING_CONSUMABLES", term) for term in printing_terms)
    if hardware:
        evidence.append(MatchedTerm("PRINTING_HARDWARE", "printer"))
    rules.extend(printing_rules)

    evidence = sorted(set(evidence), key=lambda item: (DEMAND_FAMILIES.index(item.family), item.term))
    families = tuple(family for family in DEMAND_FAMILIES if any(item.family == family for item in evidence))
    rules.extend(f"FAMILY.{family}.TERM" for family in families)

    state = "NO_GOVERNED_DEMAND_MATCH"
    state_source = title
    for candidate in ("MAINTENANCE_CALIBRATION", "RENTAL_SUBSCRIPTION_LICENSE", "MEDIA_SERVICE", "CONSULTING_OR_LABOR_SERVICE", "INSTALLATION_CONTEXT", "SERVICE_CONTEXT", "CONNECTIVITY_SERVICE"):
        if any(_has(state_source, term) for term in _CONTEXT[candidate]):
            state = candidate
            break
    else:
        purchase = any(_has(title, term) for term in _CONTEXT["PURCHASE_EXPLICIT"])
        consumable_only = consumable and not any(
            family != "PRINTING_CONSUMABLES" for family in families
        )
        if consumable_only or _has(title, "centrifuge tube"):
            state = "PARTS_CONSUMABLE"
        elif purchase:
            state = "PURCHASE_EXPLICIT"
        elif families:
            state = "PRODUCT_ONLY_UNCONTRADICTED"
        elif any(_has(corroboration, term) for term in _CONTEXT["PURCHASE_EXPLICIT"]):
            # Procurement type may corroborate state but cannot manufacture a family.
            state = "PURCHASE_EXPLICIT"
    rules.append(f"STATE.{state}")
    return DemandClassification(families, state, tuple(evidence), tuple(rules))


__all__ = ["DEMAND_FAMILIES", "SEMANTIC_STATES", "MatchedTerm", "DemandClassification", "classify_demand"]
