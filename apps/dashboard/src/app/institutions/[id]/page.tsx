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
import { findProspectById, formatIdr, loadProspects, splitExamples, splitList } from "@/lib/institution-data";

type InstitutionWorkspacePageProps = {
  params: Promise<{ id: string }>;
};

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
    return "Review CRM history and prepare follow-up notes.";
  }
  if (outreachStatus === "APPROVED") {
    return "Send approved outreach through the controlled email workflow.";
  }
  if (outreachStatus.includes("DRAFT")) {
    return "Review the draft against contact evidence and SiRUP planning context.";
  }
  if (contactStatus === "CONTACT_FOUND" && sendReadiness === "READY_FOR_CONTACT_SEARCH") {
    return "Prepare an evidence-based draft outreach for approval.";
  }
  if (contactStatus === "CONTACT_NEEDS_REVIEW") {
    return "Review contact source evidence before drafting outreach.";
  }
  return "Find or verify an official contact before drafting outreach.";
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

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Institution Workspace"
            title={institution.institution_display_name}
            description="Review who the institution is, available contacts, SiRUP planning indications, evidence status, and the next outreach action."
            actions={
              <div className="flex flex-wrap gap-2">
                <Badge tone="info">{evidenceStatus}</Badge>
                <Badge>{spseStatus}</Badge>
              </div>
            }
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Institution workspace KPIs">
          <KPI label="Need category" value={categories[0] ?? "Uncategorized"} detail={categories.length > 1 ? `${categories.length.toLocaleString("id-ID")} categories indicated by SiRUP planning records.` : "Primary category indicated by SiRUP planning records."} badge="Need" href="/outreach/prospect-queue" />
          <KPI label="Package count" value={institution.total_relevant_packages.toLocaleString("id-ID")} detail="SiRUP planning packages grouped to this institution." badge="Planning" href="/outreach/prospect-queue" />
          <KPI label="Total pagu" value={formatIdr(institution.total_pagu)} detail="Total budget from grouped planning records." badge="Pagu" href="/outreach/prospect-queue" />
          <KPI label="Outreach status" value={institution.outreach_status} detail="Current operational outreach stage for this institution." badge="Outreach" href="/outreach" />
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]" aria-label="Institution identity and contact availability">
          <Card className="p-5 md:p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">1. Institution Profile</p>
                <h2 className="mt-2 text-base font-semibold text-slate-950">Who the institution is</h2>
              </div>
              <Badge>{institution.target_level}</Badge>
            </div>
            <dl className="mt-4 grid gap-3 text-sm leading-6 text-slate-700 sm:grid-cols-2">
              <div>
                <dt className="font-medium text-slate-950">Institution ID</dt>
                <dd className="mt-1 break-all">{institution.institution_id}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Institution name</dt>
                <dd className="mt-1">{institution.institution_name}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Parent organization</dt>
                <dd className="mt-1">{institution.parent_organization || "Not provided"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Work unit</dt>
                <dd className="mt-1">{institution.work_unit || "Not provided"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Region</dt>
                <dd className="mt-1">{institution.province_or_region || "Not provided"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Location hint</dt>
                <dd className="mt-1">{institution.location_hint || "Not provided"}</dd>
              </div>
            </dl>
          </Card>

          <Card className="p-5 md:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">2. Contact Master</p>
                <h2 className="mt-2 text-base font-semibold text-slate-950">What contact is available</h2>
              </div>
              <Badge tone={badgeToneForContactStatus(institution.contact_status)}>{institution.contact_status}</Badge>
            </div>
            <dl className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
              <div>
                <dt className="font-medium text-slate-950">Email</dt>
                <dd className="mt-1 break-all">{institution.contact_email || "Not available"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Official website</dt>
                <dd className="mt-1 break-all">{institution.official_website || "Not available"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Source URL</dt>
                <dd className="mt-1 break-all">{institution.contact_source_url || "Not available"}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-950">Contact person</dt>
                <dd className="mt-1">{institution.contact_person || "Not available"}{institution.contact_role ? `, ${institution.contact_role}` : ""}</dd>
              </div>
            </dl>
          </Card>
        </section>

        <Card className="p-5 md:p-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">3. Need Intelligence</p>
              <h2 className="mt-2 text-base font-semibold text-slate-950">What needs are indicated by SiRUP</h2>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-600">{needSummary}</p>
            </div>
            <Badge tone="info">Planning evidence only</Badge>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[0.8fr_0.7fr_1.5fr]">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Need category</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {categories.length > 0 ? categories.map((category) => <Badge key={category}>{category}</Badge>) : <Badge>Uncategorized</Badge>}
              </div>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Planning totals</p>
              <p className="mt-3 text-sm font-medium leading-6 text-slate-800">{institution.total_relevant_packages.toLocaleString("id-ID")} packages</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">{formatIdr(institution.total_pagu)}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Example package names</p>
              {examples.length > 0 ? (
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                  {examples.map((example) => (
                    <li key={example}>{example}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm leading-6 text-slate-600">No example package names are available in the CSV row.</p>
              )}
            </div>
          </div>
        </Card>

        <section className="grid gap-4 lg:grid-cols-[1fr_1fr]" aria-label="Evidence support and outreach action">
          <Card className="p-5 md:p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">4. Evidence Summary</p>
            <h2 className="mt-2 text-base font-semibold text-slate-950">What evidence supports it</h2>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-4">
                <span className="font-medium text-slate-950">SiRUP evidence status</span>
                <Badge tone="info">{evidenceStatus}</Badge>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-4">
                <span className="font-medium text-slate-950">SPSE status</span>
                <Badge>{spseStatus}</Badge>
              </div>
              <div className="rounded-md border border-slate-200 bg-white p-4">
                <p className="font-medium text-slate-950">Evidence rule</p>
                <p className="mt-2 text-slate-600">Evidence is limited to SiRUP planning records in the enriched dataset. SPSE remains not checked nationally. Tender status is not inferred.</p>
              </div>
            </div>
          </Card>

          <Card className="p-5 md:p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">5. Actions</p>
            <h2 className="mt-2 text-base font-semibold text-slate-950">What outreach action is next</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge>{institution.outreach_status}</Badge>
              <Badge tone="info">{institution.send_readiness}</Badge>
              <Badge tone={badgeToneForContactStatus(institution.contact_status)}>{institution.contact_status}</Badge>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">{actionSummary}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Link href="/outreach/prospect-queue" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Back to Prospect Queue</Link>
              <Link href="/contact-master" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Review Contact</Link>
              <Link href="/outreach" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Open Outreach</Link>
              <Link href="/crm" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Open CRM</Link>
            </div>
          </Card>
        </section>

        <DraftGenerator
          institutionId={institution.institution_id}
          institutionDisplayName={institution.institution_display_name}
          contactEmail={institution.contact_email}
          categories={categories}
          packageCount={institution.total_relevant_packages}
          totalPagu={institution.total_pagu}
          examples={examples}
        />

        <section className="grid gap-4 lg:grid-cols-2" aria-label="Sales notes and next action">
          <SalesNotes institutionId={institution.institution_id} />
          <NextAction institutionId={institution.institution_id} />
        </section>


        <CommunicationTimeline institutionId={institution.institution_id} outreachStatus={institution.outreach_status} />
    </div>
  );
}






