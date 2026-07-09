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
          eyebrow="Operasi Outreach"
          title="Prospek"
          description="Antrean outreach tingkat institusi dari catatan perencanaan SiRUP 2026 untuk Mei dan Juni."
          actions={
            <div className="flex flex-wrap gap-2">
              <Badge tone="info">SIRUP_PLANNING_ONLY</Badge>
              <Badge>SPSE_NOT_CHECKED_NATIONALLY</Badge>
            </div>
          }
        />
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="KPI prospek">
        <KPI label="Total institusi" value={totalInstitutions.toLocaleString("id-ID")} detail="Seluruh institusi hasil pengelompokan SiRUP dipertahankan di CSV untuk transparansi." badge="Semua data" href="/institutions" />
        <KPI label="Kontak ditemukan" value={contactFoundCount.toLocaleString("id-ID")} detail="Email dan URL sumber tersedia pada data impor kontak." badge="Ditemukan" href="/outreach/prospect-queue" />
        <KPI label="Kontak perlu ditinjau" value={contactNeedsReviewCount.toLocaleString("id-ID")} detail="Email tersedia, tetapi URL sumber impor masih perlu ditinjau." badge="Tinjau" href="/outreach/prospect-queue" />
        <KPI label="Kontak belum ada" value={contactMissingCount.toLocaleString("id-ID")} detail="Belum ada data kontak impor yang terhubung untuk institusi ini." badge="Belum ada" href="/outreach/prospect-queue" />
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="KPI komposisi institusi">
        <KPI label="Nasional" value={nationalCount.toLocaleString("id-ID")} detail="Kementerian, lembaga nasional, dan kantor pusat tetap dapat difilter." badge="Nasional" href="/outreach/prospect-queue" />
        <KPI label="Provinsi" value={provinceCount.toLocaleString("id-ID")} detail="Institusi tingkat provinsi tetap ada dalam antrean dan tidak disembunyikan." badge="Provinsi" href="/outreach/prospect-queue" />
        <KPI label="Lokal / operasional" value={localOperationalCount.toLocaleString("id-ID")} detail="Instansi lokal, rumah sakit, pendidikan, dan unit kesehatan tetap dapat ditelusuri." badge="Lokal" href="/outreach/prospect-queue" />
        <KPI label="Perlu ditinjau" value={needsReviewCount.toLocaleString("id-ID")} detail="Institusi ambigu tetap terlihat tetapi dipisahkan untuk klasifikasi manual." badge="Tinjau" href="/outreach/prospect-queue" />
      </section>

      <Card tone="muted" className="p-4 shadow-none">
        <p className="text-sm leading-6 text-slate-600">Tabel utama menampilkan seluruh institusi. Data kontak berasal dari master yang diperkaya jika tersedia, sementara lembar impor sementara hanya digunakan sebagai fallback.</p>
        <p className="mt-2 text-sm leading-6 text-slate-600">Total pagu pada ekspor saat ini: {formatIdr(totalPagu)}</p>
      </Card>

      <ProspectQueueClient prospects={prospects} csvPath={sourceCsvPath} />
    </div>
  );
}