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
};

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
