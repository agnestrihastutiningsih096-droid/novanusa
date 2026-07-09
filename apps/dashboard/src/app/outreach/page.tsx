import Link from "next/link";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { loadProspects } from "@/lib/institution-data";
import { getAllWorkflowStates } from "@/lib/workflow-state-store";
import OutreachCenterClient from "./OutreachCenterClient";


export default function OutreachPage() {
  const institutions = loadProspects();
  const workflowStates = getAllWorkflowStates();
  const drafts = institutions.filter((item) => item.outreach_status.includes("DRAFT") || ["GENERATED", "EDITED", "SAVED"].includes(workflowStates[item.institution_id]?.draft.status ?? "")).length;
  const underTinjau = institutions.filter((item) => item.outreach_status === "UNDER_REVIEW" || workflowStates[item.institution_id]?.draft.status === "UNDER_REVIEW").length;
  const approved = institutions.filter((item) => item.outreach_status === "APPROVED" || workflowStates[item.institution_id]?.draft.approved).length;
  const readyToSend = institutions.filter((item) => item.outreach_status === "READY_TO_SEND" || workflowStates[item.institution_id]?.draft.readyToSend).length;
  const sent = institutions.filter((item) => item.outreach_status === "SENT" || workflowStates[item.institution_id]?.draft.sent).length;
  const failed = institutions.filter((item) => item.outreach_status.includes("FAILED")).length;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Pusat Outreach"
            title="Pusat Outreach"
            description="Tampilan operasional untuk draf, peninjauan, persetujuan, kesiapan kirim, terkirim, dan gagal di seluruh institusi. Pengiriman email tetap melalui mode terkontrol."
            actions={
              <div className="flex flex-wrap gap-2">
                <Link href="/outreach/prospect-queue" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Buka Prospek</Link>
                <Badge tone="info">Workflow berbasis bukti</Badge>
              </div>
            }
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6" aria-label="Pusat Outreach KPIs">
          <KPI label="Draf" value={drafts.toLocaleString("id-ID")} detail="Data dengan status draf outreach pada dataset." badge="Draf" href="/outreach" />
          <KPI label="Under Tinjau" value={underTinjau.toLocaleString("id-ID")} detail="Data yang ditandai untuk peninjauan draf jika tersedia." badge="Tinjau" href="/outreach" />
          <KPI label="Setujuid" value={approved.toLocaleString("id-ID")} detail="Setujuid records before send readiness." badge="Setujui" href="/outreach" />
          <KPI label="Siap to Send" value={readyToSend.toLocaleString("id-ID")} detail="Data yang secara eksplisit ditandai siap dikirim." badge="Siap" href="/outreach" />
          <KPI label="Terkirim" value={sent.toLocaleString("id-ID")} detail="Data yang ditandai terkirim dalam status outreach." badge="Terkirim" href="/crm" />
          <KPI label="Gagal" value={failed.toLocaleString("id-ID")} detail="Data yang ditandai gagal dalam status outreach." badge="Gagal" href="/outreach" />
        </section>

        <Card tone="muted" className="p-4 shadow-none">
          <p className="text-sm leading-6 text-slate-600">Pusat ini menggunakan data outreach institusi dan status workflow lokal/dari data. Perubahan draf di workspace disimpan melalui overlay backend lokal bila tersedia. Bukti tetap terbatas pada informasi perencanaan SiRUP; status tender tidak disimpulkan.</p>
        </Card>

        <OutreachCenterClient institutions={institutions} workflowStates={workflowStates} />
    </div>
  );
}


