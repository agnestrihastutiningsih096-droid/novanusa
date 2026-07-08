import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { formatIdr, getInstitutionCsvPath, loadProspects } from "@/lib/institution-data";
import ProspectQueueClient from "./prospect-queue-client";

export default function ProspectQueuePage() {
  const sourceCsvPath = getInstitutionCsvPath();
  const prospects = loadProspects(sourceCsvPath);
  const totalInstitutions = prospects.length;
  const nationalCount = prospects.filter((prospect) => prospect.target_level === "NATIONAL").length;
  const provinceCount = prospects.filter((prospect) => prospect.target_level === "PROVINCE").length;
  const localOperationalCount = prospects.filter((prospect) => ["LOCAL_AGENCY", "HOSPITAL", "EDUCATION", "HEALTH_UNIT"].includes(prospect.target_level)).length;
  const contactFoundCount = prospects.filter((prospect) => prospect.contact_status === "CONTACT_FOUND").length;
  const contactNeedsReviewCount = prospects.filter((prospect) => prospect.contact_status === "CONTACT_NEEDS_REVIEW").length;
  const contactMissingCount = prospects.filter((prospect) => prospect.contact_status === "CONTACT_MISSING").length;
  const needsReviewCount = prospects.filter((prospect) => prospect.send_readiness === "NEEDS_REVIEW").length;
  const totalPagu = prospects.reduce((sum, prospect) => sum + prospect.total_pagu, 0);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Outreach operations"
            title="Prospect Queue"
            description="Institution-level Mitracom outreach queue from real SiRUP 2026 planning records for May and June."
            actions={
              <div className="flex flex-wrap gap-2">
                <Badge tone="info">SIRUP_PLANNING_ONLY</Badge>
                <Badge>SPSE_NOT_CHECKED_NATIONALLY</Badge>
              </div>
            }
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Prospect queue KPIs">
          <KPI label="Total institutions" value={totalInstitutions.toLocaleString("id-ID")} detail="All grouped SiRUP institutions kept in the CSV for transparency." badge="All rows" href="/institutions" />
          <KPI label="CONTACT_FOUND" value={contactFoundCount.toLocaleString("id-ID")} detail="Email and source URL are present in the contact import file." badge="Found" href="/outreach/prospect-queue" />
          <KPI label="CONTACT_NEEDS_REVIEW" value={contactNeedsReviewCount.toLocaleString("id-ID")} detail="Email exists, but the import source URL still needs review." badge="Review" href="/outreach/prospect-queue" />
          <KPI label="CONTACT_MISSING" value={contactMissingCount.toLocaleString("id-ID")} detail="No imported contact data has been linked for this institution." badge="Missing" href="/outreach/prospect-queue" />
        </section>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Institution mix KPIs">
          <KPI label="National" value={nationalCount.toLocaleString("id-ID")} detail="Ministries, national bodies, and central offices remain filterable targets." badge="National" href="/outreach/prospect-queue" />
          <KPI label="Province" value={provinceCount.toLocaleString("id-ID")} detail="Province-level institutions remain in the queue and are not hidden." badge="Province" href="/outreach/prospect-queue" />
          <KPI label="Local / operational" value={localOperationalCount.toLocaleString("id-ID")} detail="Local agencies, hospitals, education, and health units ready for search." badge="Local" href="/outreach/prospect-queue" />
          <KPI label="Needs review" value={needsReviewCount.toLocaleString("id-ID")} detail="Ambiguous institutions remain visible but are separated for manual classification." badge="Review" href="/outreach/prospect-queue" />
        </section>

        <Card tone="muted" className="p-4 shadow-none">
          <p className="text-sm leading-6 text-slate-600">The default table shows all institutions. Contact data comes from the enriched master join when available, with the temporary import sheet used only as a fallback.</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">Total pagu in the current export: {formatIdr(totalPagu)}</p>
        </Card>

        <ProspectQueueClient prospects={prospects} csvPath={sourceCsvPath} />
    </div>
  );
}
