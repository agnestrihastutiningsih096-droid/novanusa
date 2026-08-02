import fs from "fs";
import path from "path";

export type Prospect = {
  institution_id: string;
  institution_name: string;
  institution_display_name: string;
  parent_organization: string;
  work_unit: string;
  province_or_region: string;
  location_hint: string;
  target_level: string;
  send_readiness: string;
  total_relevant_packages: number;
  total_pagu: number;
  months_found: string;
  relevant_categories: string;
  example_package_names: string;
  evidence_status: string;
  spse_status: string;
  contact_status: string;
  outreach_status: string;
  contact_email: string;
  official_website: string;
  contact_source_url: string;
  contact_phone: string;
  contact_whatsapp: string;
  contact_person: string;
  contact_role: string;
  contact_notes: string;
  contactVerificationStatus: string;
  contactVerifiedAt: string;
  contactVerifiedBy: string;
  contactVerificationSource: string;
};

export type ContactVerificationResult =
  | { ok: true; snapshot: ContactVerificationSnapshot }
  | { ok: false; code: string };

export type ContactVerificationSnapshot = {
  institutionId: string;
  email: string;
  status: "VERIFIED";
  verifiedAt: string;
  verifiedBy: string;
  sourceUrl: string;
  verificationSource: string;
};

export function validateVerifiedContact(prospect: Prospect, expectedInstitutionId: string): ContactVerificationResult {
  if (prospect.institution_id !== expectedInstitutionId) return { ok: false, code: "CONTACT_INSTITUTION_MISMATCH" };
  const email = prospect.contact_email.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { ok: false, code: "CONTACT_EMAIL_INVALID" };
  if (!prospect.contact_source_url.trim()) return { ok: false, code: "CONTACT_SOURCE_MISSING" };
  if (prospect.contact_status.trim().toUpperCase() === "CONTACT_NEEDS_REVIEW") return { ok: false, code: "CONTACT_NEEDS_REVIEW" };
  if (prospect.contact_status.trim().toUpperCase() !== "CONTACT_FOUND") return { ok: false, code: "CONTACT_STATUS_NOT_VERIFIED" };
  const status = prospect.contactVerificationStatus.trim().toUpperCase();
  if (status !== "VERIFIED") return { ok: false, code: status ? `CONTACT_${status}` : "CONTACT_VERIFICATION_MISSING" };
  if (!prospect.contactVerifiedAt.trim() || !prospect.contactVerifiedBy.trim() || !prospect.contactVerificationSource.trim()) {
    return { ok: false, code: "CONTACT_VERIFICATION_INCOMPLETE" };
  }
  return {
    ok: true,
    snapshot: {
      institutionId: prospect.institution_id,
      email,
      status: "VERIFIED",
      verifiedAt: prospect.contactVerifiedAt,
      verifiedBy: prospect.contactVerifiedBy,
      sourceUrl: prospect.contact_source_url,
      verificationSource: prospect.contactVerificationSource,
    },
  };
}

export const outreachCsvPath = path.resolve(
  process.cwd(),
  "..",
  "..",
  "outputs",
  "dashboard",
  "mitracom_sirup_institution_outreach_may_june_2026.csv",
);

export const enrichedCsvPath = path.resolve(
  process.cwd(),
  "..",
  "..",
  "outputs",
  "dashboard",
  "mitracom_sirup_institution_outreach_enriched.csv",
);

const contactImportCsvPath = path.resolve(
  process.cwd(),
  "..",
  "..",
  "outputs",
  "dashboard",
  "contact_import_mitracom_may_june_2026.csv",
);

function parseCsv(text: string): Array<Record<string, string>> {
  const rows: string[][] = [];
  let current = "";
  let row: string[] = [];
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === "\"" && quoted && next === "\"") {
      current += "\"";
      index += 1;
      continue;
    }

    if (char === "\"") {
      quoted = !quoted;
      continue;
    }

    if (char === "," && !quoted) {
      row.push(current);
      current = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(current);
      if (row.some((value) => value.length > 0)) {
        rows.push(row);
      }
      row = [];
      current = "";
      continue;
    }

    current += char;
  }

  if (current || row.length > 0) {
    row.push(current);
    rows.push(row);
  }

  const [headers = [], ...dataRows] = rows;
  return dataRows.map((values) => Object.fromEntries(headers.map((header, index) => [header.replace(/^\uFEFF/, ""), values[index] ?? ""])));
}

function loadRows(csvPath: string) {
  if (!fs.existsSync(csvPath)) {
    return [] as Array<Record<string, string>>;
  }

  return parseCsv(fs.readFileSync(csvPath, "utf8"));
}

function hashId(value: string) {
  let hash = 0;

  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }

  return hash.toString(36);
}

export function buildInstitutionId(name: string) {
  const slug = name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

  return `${slug || "institution"}-${hashId(name)}`;
}

function toProspect(record: Record<string, string>): Prospect {
  const institutionName = record.institution_name;

  return {
    institution_id: buildInstitutionId(institutionName),
    institution_name: institutionName,
    institution_display_name: record.institution_display_name || institutionName,
    parent_organization: record.parent_organization,
    work_unit: record.work_unit,
    province_or_region: record.province_or_region,
    location_hint: record.location_hint,
    target_level: record.target_level,
    send_readiness: record.send_readiness,
    total_relevant_packages: Number(record.total_relevant_packages || 0),
    total_pagu: Number(record.total_pagu || 0),
    months_found: record.months_found,
    relevant_categories: record.relevant_categories,
    example_package_names: record.example_package_names,
    evidence_status: record.evidence_status,
    spse_status: record.spse_status,
    contact_status: record.contact_status,
    outreach_status: record.outreach_status,
    contact_email: record.contact_email || "",
    official_website: record.official_website || "",
    contact_source_url: record.contact_source_url || "",
    contact_phone: record.contact_phone || "",
    contact_whatsapp: record.contact_whatsapp || "",
    contact_person: record.contact_person || "",
    contact_role: record.contact_role || "",
    contact_notes: record.contact_notes || "",
    contactVerificationStatus: record.contactVerificationStatus || record.contact_verification_status || "",
    contactVerifiedAt: record.contactVerifiedAt || record.contact_verified_at || "",
    contactVerifiedBy: record.contactVerifiedBy || record.contact_verified_by || "",
    contactVerificationSource: record.contactVerificationSource || record.contact_verification_source || "",
  };
}

function mergeContacts(prospects: Prospect[]): Prospect[] {
  const contactRows = loadRows(contactImportCsvPath);
  const contactByInstitution = new Map<string, Record<string, string>>();

  for (const row of contactRows) {
    const institution = (row.institution_name ?? "").trim();
    if (institution) {
      contactByInstitution.set(institution, row);
    }
  }

  return prospects.map((prospect) => {
    const contact = contactByInstitution.get(prospect.institution_name);
    const contactEmail = contact?.contact_email?.trim() ?? "";
    const contactSourceUrl = contact?.contact_source_url?.trim() ?? "";

    let contactStatus = "CONTACT_MISSING";
    if (contactEmail && contactSourceUrl) {
      contactStatus = "CONTACT_FOUND";
    } else if (contactEmail && !contactSourceUrl) {
      contactStatus = "CONTACT_NEEDS_REVIEW";
    }

    return {
      ...prospect,
      contact_status: contactStatus,
      contact_email: contactEmail,
      official_website: contact?.official_website?.trim() ?? "",
      contact_source_url: contactSourceUrl,
      contactVerificationStatus: contact?.contactVerificationStatus?.trim() || contact?.contact_verification_status?.trim() || "",
      contactVerifiedAt: contact?.contactVerifiedAt?.trim() || contact?.contact_verified_at?.trim() || "",
      contactVerifiedBy: contact?.contactVerifiedBy?.trim() || contact?.contact_verified_by?.trim() || "",
      contactVerificationSource: contact?.contactVerificationSource?.trim() || contact?.contact_verification_source?.trim() || "",
    };
  });
}

export function getInstitutionCsvPath() {
  return fs.existsSync(enrichedCsvPath) ? enrichedCsvPath : outreachCsvPath;
}

export function loadProspects(sourceCsvPath = getInstitutionCsvPath()): Prospect[] {
  const prospects = loadRows(sourceCsvPath).map(toProspect);

  if (sourceCsvPath === enrichedCsvPath) {
    return prospects;
  }

  return mergeContacts(prospects);
}

export function findProspectById(id: string) {
  return loadProspects().find((prospect) => prospect.institution_id === id);
}

export function splitList(value: string) {
  return value.split(";").map((item) => item.trim()).filter(Boolean);
}

export function splitExamples(value: string) {
  return value.split("|").map((item) => item.trim()).filter(Boolean);
}

export function formatIdr(value: number) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}
