import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { formatIdr, loadProspects } from "@/lib/institution-data";
import InstitusiClient from "./institutions-client";

type KontakFilter = "ALL" | "FOUND" | "MISSING";
type BuktiFilter = "ALL" | "SIRUP_PLANNING_ONLY";

type InstitusiPageProps = {
  searchParams: Promise<{ contact?: string; evidence?: string }>;
};

function contactFilterFromParam(value?: string): KontakFilter {
  if (value === "found") {
    return "FOUND";
  }

  if (value === "missing") {
    return "MISSING";
  }

  return "ALL";
}

function evidenceFilterFromParam(value?: string): BuktiFilter {
  if (value === "sirup") {
    return "SIRUP_PLANNING_ONLY";
  }

  return "ALL";
}

export default async function InstitusiPage({ searchParams }: InstitusiPageProps) {
  const params = await searchParams;
  const institutions = loadProspects();
  const totalPagu = institutions.reduce((sum, institution) => sum + institution.total_pagu, 0);
  const contactFoundCount = institutions.filter((institution) => institution.contact_email.trim().length > 0).length;
  const planningOnlyCount = institutions.filter((institution) => institution.evidence_status === "SIRUP_PLANNING_ONLY").length;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Operasi Institusi"
            title="Institusi"
            description="Telusuri data institusi dan buka workspace untuk meninjau profil, kontak, kebutuhan, bukti, outreach, dan CRM."
            actions={<Badge tone="info">Workspace Institusi</Badge>}
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Institusi KPIs">
          <KPI label="Total institusi" value={institutions.length.toLocaleString("id-ID")} detail="Data institusi yang dimuat dari dataset outreach yang diperkaya." badge="Records" href="/institutions" />
          <KPI label="Bukti perencanaan SiRUP" value={planningOnlyCount.toLocaleString("id-ID")} detail="Data yang ditandai sebagai bukti perencanaan saja." badge="SiRUP" href="/institutions?evidence=sirup" />
          <KPI label="Kontak ditemukan" value={contactFoundCount.toLocaleString("id-ID")} detail="Data institusi dengan email kontak tersedia untuk ditinjau." badge="Kontak" href="/institutions?contact=found" />
          <KPI label="Total pagu" value={formatIdr(totalPagu)} detail="Pagu perencanaan yang dikelompokkan pada dataset institusi." badge="Pagu" href="/outreach/prospect-queue" />
        </section>

        <InstitusiClient
          key={`${params.contact ?? "all"}-${params.evidence ?? "all"}`}
          institutions={institutions}
          initialContactFilter={contactFilterFromParam(params.contact)}
          initialEvidenceFilter={evidenceFilterFromParam(params.evidence)}
        />
    </div>
  );
}
