import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { formatIdr, loadProspects } from "@/lib/institution-data";
import InstitutionsClient from "./institutions-client";

type ContactFilter = "ALL" | "FOUND" | "MISSING";
type EvidenceFilter = "ALL" | "SIRUP_PLANNING_ONLY";

type InstitutionsPageProps = {
  searchParams: Promise<{ contact?: string; evidence?: string }>;
};

function contactFilterFromParam(value?: string): ContactFilter {
  if (value === "found") {
    return "FOUND";
  }

  if (value === "missing") {
    return "MISSING";
  }

  return "ALL";
}

function evidenceFilterFromParam(value?: string): EvidenceFilter {
  if (value === "sirup") {
    return "SIRUP_PLANNING_ONLY";
  }

  return "ALL";
}

export default async function InstitutionsPage({ searchParams }: InstitutionsPageProps) {
  const params = await searchParams;
  const institutions = loadProspects();
  const totalPagu = institutions.reduce((sum, institution) => sum + institution.total_pagu, 0);
  const contactFoundCount = institutions.filter((institution) => institution.contact_email.trim().length > 0).length;
  const planningOnlyCount = institutions.filter((institution) => institution.evidence_status === "SIRUP_PLANNING_ONLY").length;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Institution operations"
            title="Institutions"
            description="Browse institution records and open the workspace for profile, contact, need, evidence, outreach, and CRM review."
            actions={<Badge tone="info">Institution Workspace</Badge>}
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Institution KPIs">
          <KPI label="Total institutions" value={institutions.length.toLocaleString("id-ID")} detail="Institution records loaded from the enriched outreach dataset." badge="Records" href="/institutions" />
          <KPI label="SiRUP planning evidence" value={planningOnlyCount.toLocaleString("id-ID")} detail="Records marked as planning-only evidence." badge="SiRUP" href="/institutions?evidence=sirup" />
          <KPI label="Contact found" value={contactFoundCount.toLocaleString("id-ID")} detail="Institution records with contact email available for review." badge="Contact" href="/institutions?contact=found" />
          <KPI label="Total pagu" value={formatIdr(totalPagu)} detail="Grouped planning budget across the institution dataset." badge="Pagu" href="/outreach/prospect-queue" />
        </section>

        <InstitutionsClient
          key={`${params.contact ?? "all"}-${params.evidence ?? "all"}`}
          institutions={institutions}
          initialContactFilter={contactFilterFromParam(params.contact)}
          initialEvidenceFilter={evidenceFilterFromParam(params.evidence)}
        />
    </div>
  );
}
