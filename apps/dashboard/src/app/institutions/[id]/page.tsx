import Link from "next/link";
import { notFound } from "next/navigation";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import DraftGenerator from "./DraftGenerator";
import CommunicationTimeline from "./CommunicationTimeline";
import SalesNotes from "./SalesNotes";
import NextAction from "./NextAction";
import CommunicationOutcome from "./CommunicationOutcome";
import ContactVerificationAction from "./ContactVerificationAction";
import { InstitutionOperatorProvider } from "./InstitutionOperatorContext";
import { CONTACT_VERIFICATION_SOURCE, createContactFingerprint, getMatchingContactVerification } from "@/lib/contact-verification";
import { getContactVerification } from "@/lib/contact-verification-store";
import { findProspectById, formatIdr, loadProspects, splitExamples, splitList } from "@/lib/institution-data";
import { applyEffectiveContact, resolveEffectiveContact } from "@/lib/contact-override";
import { getContactOverrideEvents } from "@/lib/contact-override-store";

type InstitutionWorkspacePageProps = {
  params: Promise<{ id: string }>;
};

export const dynamic = "force-dynamic";

function badgeToneForContactStatus(value: string) {
  if (value === "CONTACT_FOUND") {
    return "success";
  }
  if (value === "CONTACT_NEEDS_REVIEW") {
    return "warning";
  }
  return "neutral";
}

function buildNeedSummary(categories: string[], packageCount: number, totalPagu: number, examples: string[]) {
  const categoryText = categories.length > 0 ? categories.join(", ") : "kategori yang belum terklasifikasi";
  const exampleText = examples.length > 0 ? ` Contoh paket yang tercatat: ${examples.slice(0, 3).join("; ")}.` : "";

  return `Berdasarkan informasi rencana pengadaan yang dipublikasikan melalui SiRUP, institusi ini memiliki indikasi area kebutuhan pada ${categoryText}. Ringkasan ini berasal dari ${packageCount.toLocaleString("id-ID")} paket rencana dengan total pagu ${formatIdr(totalPagu)}.${exampleText}`;
}

function nextOutreachAction(contactStatus: string, sendReadiness: string, outreachStatus: string) {
  if (outreachStatus === "SENT") {
    return "Tinjau histori CRM dan siapkan catatan tindak lanjut.";
  }
  if (outreachStatus === "APPROVED") {
    return "Kirim outreach yang sudah disetujui melalui workflow email terkontrol.";
  }
  if (outreachStatus.includes("DRAFT")) {
    return "Tinjau draf terhadap bukti kontak dan konteks perencanaan SiRUP.";
  }
  if (contactStatus === "CONTACT_FOUND" && sendReadiness === "READY_FOR_CONTACT_SEARCH") {
    return "Siapkan draf outreach berbasis bukti untuk persetujuan.";
  }
  if (contactStatus === "CONTACT_NEEDS_REVIEW") {
    return "Tinjau bukti sumber kontak sebelum menyusun outreach.";
  }
  return "Temukan atau verifikasi kontak resmi sebelum menyusun outreach.";
}

export function generateStaticParams() {
  return loadProspects().map((prospect) => ({ id: prospect.institution_id }));
}

export default async function InstitutionWorkspacePage({ params }: InstitutionWorkspacePageProps) {
  const { id } = await params;
  const institution = findProspectById(id);

  if (!institution) {
    notFound();
  }

  const categories = splitList(institution.relevant_categories);
  const examples = splitExamples(institution.example_package_names).slice(0, 6);
  const evidenceStatus = "SIRUP_PLANNING_ONLY";
  const spseStatus = "SPSE_NOT_CHECKED_NATIONALLY";
  const needSummary = buildNeedSummary(categories, institution.total_relevant_packages, institution.total_pagu, examples);
  const actionSummary = nextOutreachAction(institution.contact_status, institution.send_readiness, institution.outreach_status);
  const overrideEvents = getContactOverrideEvents(id);
  const effectiveContact = resolveEffectiveContact(institution, overrideEvents);
  const effectiveInstitution = effectiveContact ? applyEffectiveContact(institution, effectiveContact) : institution;
  const contactFingerprint = effectiveContact?.fingerprint ?? createContactFingerprint(institution.institution_id, institution.contact_email, institution.contact_source_url, CONTACT_VERIFICATION_SOURCE);
  const persistedVerification = effectiveContact ? getMatchingContactVerification(effectiveInstitution, getContactVerification(id)) : null;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Workspace Institusi"
            title={institution.institution_display_name}
            description="Tinjau profil institusi, kontak yang tersedia, indikasi kebutuhan dari SiRUP, status bukti, dan aksi outreach berikutnya."
            actions={
              <div className="flex flex-wrap gap-2">
                <Badge tone="info">{evidenceStatus}</Badge>
                <Badge>{spseStatus}</Badge>
              </div>
            }
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Institution workspace KPIs">
          <KPI label="Kategori kebutuhan" value={categories[0] ?? "Belum terkategori"} detail={categories.length > 1 ? `${categories.length.toLocaleString("id-ID")} kategori terindikasi dari catatan perencanaan SiRUP.` : "Kategori utama terindikasi dari catatan perencanaan SiRUP."} badge="Need" href="/outreach/prospect-queue" />
          <KPI label="Jumlah paket" value={institution.total_relevant_packages.toLocaleString("id-ID")} detail="Paket perencanaan SiRUP yang dikelompokkan ke institusi ini." badge="Planning" href="/outreach/prospect-queue" />
          <KPI label="Total pagu" value={formatIdr(institution.total_pagu)} detail="Total pagu dari catatan perencanaan yang dikelompokkan." badge="Pagu" href="/outreach/prospect-queue" />
          <KPI label="Status outreach" value={institution.outreach_status} detail="Tahap operasional outreach saat ini untuk institusi ini." badge="Outreach" href="/outreach" />
        </section>

        <InstitutionOperatorProvider>
        <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]" aria-label="Institution identity and contact availability">
          <Card className="p-5 md:p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">1. Profil Institusi</p>
                <h2 className="mt-2 text-base font-semibold text-slate-950">Identitas institusi</h2>
              </div>
              <Badge>{institution.target_level}</Badge>
            </div>
            <dl className="mt-4 grid gap-3 text-sm leading-6 text-slate-700 sm:grid-cols-2">
              <div>
                <dt className="font-medium text-slate-950">ID Institusi</dt>
                <dd className="mt-1 break-all">{institution.institution_id}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Nama institusi</dt>
                <dd className="mt-1">{institution.institution_name}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Organisasi induk</dt>
                <dd className="mt-1">{institution.parent_organization || "Tidak tersedia"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Unit kerja</dt>
                <dd className="mt-1">{institution.work_unit || "Tidak tersedia"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Wilayah</dt>
                <dd className="mt-1">{institution.province_or_region || "Tidak tersedia"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Petunjuk lokasi</dt>
                <dd className="mt-1">{institution.location_hint || "Tidak tersedia"}</dd>
              </div>
            </dl>
            <ContactVerificationAction
              institutionId={institution.institution_id}
              contactEmail={effectiveContact?.email ?? ""}
              evidenceUrl={effectiveContact?.sourceUrl ?? ""}
              expectedContactFingerprint={contactFingerprint}
              verificationSource={CONTACT_VERIFICATION_SOURCE}
              initialVerification={persistedVerification}
              initialEvents={overrideEvents}
            />
          </Card>

          <Card className="p-5 md:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">2. Master Kontak</p>
                <h2 className="mt-2 text-base font-semibold text-slate-950">Kontak yang tersedia</h2>
              </div>
              <Badge tone={badgeToneForContactStatus(institution.contact_status)}>{institution.contact_status}</Badge>
            </div>
            <dl className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
              <div>
                <dt className="font-medium text-slate-950">Email</dt>
                <dd className="mt-1 break-all">{institution.contact_email || "Tidak tersedia"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Situs resmi</dt>
                <dd className="mt-1 break-all">{institution.official_website || "Tidak tersedia"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">URL sumber</dt>
                <dd className="mt-1 break-all">{institution.contact_source_url || "Tidak tersedia"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Narahubung</dt>
                <dd className="mt-1">{institution.contact_person || "Tidak tersedia"}{institution.contact_role ? `, ${institution.contact_role}` : ""}</dd>
              </div>
            </dl>
          </Card>
        </section>

        <Card className="p-5 md:p-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">3. Intelijen Kebutuhan</p>
              <h2 className="mt-2 text-base font-semibold text-slate-950">Kebutuhan yang terindikasi dari SiRUP</h2>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-600">{needSummary}</p>
            </div>
            <Badge tone="info">Hanya bukti perencanaan</Badge>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[0.8fr_0.7fr_1.5fr]">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Kategori kebutuhan</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {categories.length > 0 ? categories.map((category) => <Badge key={category}>{category}</Badge>) : <Badge>Belum terkategori</Badge>}
              </div>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Total perencanaan</p>
              <p className="mt-3 text-sm font-medium leading-6 text-slate-800">{institution.total_relevant_packages.toLocaleString("id-ID")} paket</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">{formatIdr(institution.total_pagu)}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Contoh nama paket</p>
              {examples.length > 0 ? (
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                  {examples.map((example) => (
                    <li key={example}>{example}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm leading-6 text-slate-600">Tidak ada contoh nama paket pada baris CSV ini.</p>
              )}
            </div>
          </div>
        </Card>

        <section className="grid gap-4 lg:grid-cols-[1fr_1fr]" aria-label="Evidence support and outreach action">
          <Card className="p-5 md:p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">4. Ringkasan Bukti</p>
            <h2 className="mt-2 text-base font-semibold text-slate-950">Bukti yang mendukung</h2>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-4">
                <span className="font-medium text-slate-950">Status bukti SiRUP</span>
                <Badge tone="info">{evidenceStatus}</Badge>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-4">
                <span className="font-medium text-slate-950">Status SPSE</span>
                <Badge>{spseStatus}</Badge>
              </div>
              <div className="rounded-md border border-slate-200 bg-white p-4">
                <p className="font-medium text-slate-950">Aturan bukti</p>
                <p className="mt-2 text-slate-600">Bukti terbatas pada catatan perencanaan SiRUP di dataset yang diperkaya. SPSE belum dicek secara nasional. Status tender tidak disimpulkan.</p>
              </div>
            </div>
          </Card>

          <Card className="p-5 md:p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">5. Aksi</p>
            <h2 className="mt-2 text-base font-semibold text-slate-950">Aksi outreach berikutnya</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge>{institution.outreach_status}</Badge>
              <Badge tone="info">{institution.send_readiness}</Badge>
              <Badge tone={badgeToneForContactStatus(institution.contact_status)}>{institution.contact_status}</Badge>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">{actionSummary}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Link href="/outreach/prospect-queue" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Kembali ke Prospek</Link>
              <Link href="/contact-master" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Tinjau Kontak</Link>
              <Link href="/outreach" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Buka Outreach</Link>
              <Link href="/crm" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Buka CRM</Link>
            </div>
          </Card>
        </section>

        <DraftGenerator
          institutionId={institution.institution_id}
          institutionDisplayName={institution.institution_display_name}
          contactEmail={effectiveContact?.email ?? ""}
          categories={categories}
          packageCount={institution.total_relevant_packages}
          totalPagu={institution.total_pagu}
          examples={examples}
          monthsFound={institution.months_found}
        />

        <section className="grid gap-4 lg:grid-cols-2" aria-label="Sales notes and next action">
          <SalesNotes institutionId={institution.institution_id} />
          <NextAction institutionId={institution.institution_id} />
        </section>

        <CommunicationOutcome institutionId={institution.institution_id} />


        <CommunicationTimeline institutionId={institution.institution_id} outreachStatus={institution.outreach_status} />
        </InstitutionOperatorProvider>
    </div>
  );
}






