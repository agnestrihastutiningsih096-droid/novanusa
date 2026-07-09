import Link from "next/link";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import PageHeader from "@/components/common/PageHeader";
import { labelForStatus } from "@/lib/display-labels";
import { formatIdr, loadProspects, splitList } from "@/lib/institution-data";
import { getAllWorkflowStates } from "@/lib/workflow-state-store";

function countDrafts(status: string) {
  return status.includes("DRAFT");
}

export default function Home() {
  const institutions = loadProspects();
  const workflowStates = getAllWorkflowStates();
  const totalNeeds = institutions.reduce((sum, item) => sum + item.total_relevant_packages, 0);
  const outreachCount = institutions.filter((item) => item.outreach_status !== "NOT_CONTACTED" || Boolean(workflowStates[item.institution_id]?.draft.updatedAt)).length;
  const readyToSendCount = institutions.filter((item) => item.outreach_status === "READY_TO_SEND" || workflowStates[item.institution_id]?.draft.readyToSend).length;
  const waitingApprovalCount = institutions.filter((item) => item.outreach_status === "UNDER_REVIEW" || countDrafts(item.outreach_status) || workflowStates[item.institution_id]?.draft.status === "UNDER_REVIEW").length;
  const draftsCount = institutions.filter((item) => countDrafts(item.outreach_status) || ["GENERATED", "EDITED", "SAVED"].includes(workflowStates[item.institution_id]?.draft.status ?? "")).length;
  const followUpsCount = institutions.filter((item) => item.outreach_status === "SENT" || workflowStates[item.institution_id]?.draft.sent).length;
  const recentInstitutions = institutions.slice(0, 8);

  const kpis = [
    { label: "Institusi", value: institutions.length.toLocaleString("id-ID"), detail: "Data institusi dalam dataset outreach yang diperkaya.", href: "/institutions", badge: "Data" },
    { label: "Kebutuhan Pengadaan", value: totalNeeds.toLocaleString("id-ID"), detail: "Paket perencanaan SiRUP yang dikelompokkan per institusi.", href: "/outreach/prospect-queue", badge: "SiRUP" },
    { label: "Outreach", value: outreachCount.toLocaleString("id-ID"), detail: "Data yang sudah melewati tahap belum dihubungi.", href: "/outreach", badge: "Alur" },
    { label: "Siap Dikirim", value: readyToSendCount.toLocaleString("id-ID"), detail: "Data yang secara eksplisit ditandai siap dikirim.", href: "/outreach", badge: "Siap" },
  ];

  const todayWork = [
    { label: "Siap Dikirim", value: readyToSendCount, href: "/outreach" },
    { label: "Menunggu Persetujuan", value: waitingApprovalCount, href: "/outreach" },
    { label: "Draf", value: draftsCount, href: "/outreach" },
    { label: "Tindak Lanjut", value: followUpsCount, href: "/crm" },
  ];

  const workflow = [
    { label: "Prospek", href: "/outreach/prospect-queue" },
    { label: "Workspace Institusi", href: "/institutions" },
    { label: "Draf", href: "/outreach" },
    { label: "Persetujuan", href: "/outreach" },
    { label: "Kirim", href: "/outreach" },
    { label: "CRM", href: "/crm" },
  ];

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Card className="p-6 md:p-7">
        <PageHeader
          eyebrow="Beranda"
          title="Dashboard NovaNusa"
          description="Intelijen pengadaan berbasis bukti untuk operasi sales harian. Pilih institusi, tinjau bukti perencanaan SiRUP, siapkan outreach, dan catat komunikasi."
          actions={<Badge tone="info">Fase 1 siap sales</Badge>}
        />
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="KPI Beranda">
        {kpis.map((kpi) => (
          <Link key={kpi.label} href={kpi.href} className="block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400">
            <Card className="h-full p-5 transition-colors hover:bg-slate-50">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-500">{kpi.label}</p>
                  <p className="mt-3 text-2xl font-semibold tracking-normal text-slate-950">{kpi.value}</p>
                </div>
                <Badge>{kpi.badge}</Badge>
              </div>
              <p className="mt-3 text-sm leading-5 text-slate-500">{kpi.detail}</p>
            </Card>
          </Link>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <Card className="p-5 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Pekerjaan Hari Ini</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            {todayWork.map((item) => (
              <Link key={item.label} href={item.href} className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-4 py-3 transition-colors hover:bg-slate-50">
                <span className="text-sm font-medium text-slate-700">{item.label}</span>
                <span className="text-base font-semibold text-slate-950">{item.value.toLocaleString("id-ID")}</span>
              </Link>
            ))}
          </div>
        </Card>

        <Card className="p-5 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Workflow</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            {workflow.map((step, index) => (
              <Link key={step.label} href={step.href} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3 transition-colors hover:bg-white">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex size-6 items-center justify-center rounded-md border border-slate-200 bg-white text-xs font-semibold text-slate-500">{index + 1}</span>
                  {index < workflow.length - 1 ? <span className="text-xs text-slate-300">-&gt;</span> : null}
                </div>
                <p className="mt-3 text-sm font-medium text-slate-800">{step.label}</p>
              </Link>
            ))}
          </div>
        </Card>
      </section>

      <Card className="overflow-hidden">
        <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Institusi Terbaru</p>
          <h2 className="mt-1 text-base font-semibold text-slate-950">Mulai dari workspace institusi</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              <tr>
                <th className="border-b border-slate-200 px-5 py-3">Institusi</th>
                <th className="border-b border-slate-200 px-5 py-3">Kategori kebutuhan</th>
                <th className="border-b border-slate-200 px-5 py-3">Status outreach</th>
                <th className="border-b border-slate-200 px-5 py-3">Email kontak</th>
                <th className="border-b border-slate-200 px-5 py-3">Pagu</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/80 bg-white">
              {recentInstitutions.map((institution) => (
                <tr key={institution.institution_id} className="align-top transition-colors hover:bg-slate-50/80">
                  <td className="max-w-[340px] px-5 py-4">
                    <Link href={`/institutions/${institution.institution_id}`} className="font-medium text-slate-950 underline-offset-4 hover:text-blue-700 hover:underline">
                      {institution.institution_display_name}
                    </Link>
                  </td>
                  <td className="max-w-[240px] px-5 py-4 text-slate-600">{splitList(institution.relevant_categories).join(", ") || "Belum terkategori"}</td>
                  <td className="px-5 py-4"><Badge>{labelForStatus(institution.outreach_status)}</Badge></td>
                  <td className="max-w-[220px] px-5 py-4 text-xs leading-5 text-slate-600">{institution.contact_email || "Email kontak belum tersedia"}</td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">{formatIdr(institution.total_pagu)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}