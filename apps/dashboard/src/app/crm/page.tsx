import Link from "next/link";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { currentTimelineLabel, timelineEvents, completedTimelineKeysFromOutreachStatus } from "@/lib/crm-timeline";
import { loadProspects, splitList } from "@/lib/institution-data";
import { getAllWorkflowStates } from "@/lib/workflow-state-store";

export default function CrmPage() {
  const institutions = loadProspects();
  const workflowStates = getAllWorkflowStates();
  const eventCounts = timelineEvents.map((event) => ({
    ...event,
    count: institutions.filter((institution) => completedTimelineKeysFromOutreachStatus(institution.outreach_status).has(event.key) || workflowStates[institution.institution_id]?.timeline.completedEvents.includes(event.key)).length,
  }));
  const activeTimelineRows = institutions
    .filter((institution) => completedTimelineKeysFromOutreachStatus(institution.outreach_status).size > 0 || (workflowStates[institution.institution_id]?.timeline.completedEvents.length ?? 0) > 0)
    .slice(0, 20);
  const followUpCount = eventCounts.filter((event) => event.key === "FOLLOW_UP_1" || event.key === "FOLLOW_UP_2").reduce((sum, event) => sum + event.count, 0);
  const sentCount = eventCounts.find((event) => event.key === "EMAIL_SENT")?.count ?? 0;
  const approvedCount = eventCounts.find((event) => event.key === "DRAFT_APPROVED")?.count ?? 0;
  const draftedCount = eventCounts.find((event) => event.key === "COLD_EMAIL_DRAFTED")?.count ?? 0;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="CRM"
            title="CRM Timeline"
            description="Institution-centric communication timeline summary for outreach follow-up and communication history. Workspace timeline edits are local until backend persistence is added."
            actions={<Badge tone="info">Local timeline v1</Badge>}
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="CRM timeline KPIs">
          <KPI label="Cold email drafted" value={draftedCount.toLocaleString("id-ID")} detail="Records with data-derived drafted status." badge="Drafted" href="/outreach" />
          <KPI label="Draft approved" value={approvedCount.toLocaleString("id-ID")} detail="Records with approved or later outreach state." badge="Approved" href="/outreach" />
          <KPI label="Email sent" value={sentCount.toLocaleString("id-ID")} detail="Placeholder send state derived from outreach status." badge="Sent" href="/crm" />
          <KPI label="Follow-ups" value={followUpCount.toLocaleString("id-ID")} detail="Follow-up events are local workspace timeline entries for now." badge="Follow-up" href="/crm" />
        </section>

        <Card className="p-5 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Timeline stages</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {eventCounts.map((event) => (
              <div key={event.key} className="rounded-md border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-950">{event.label}</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">{event.count.toLocaleString("id-ID")}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{event.description}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="overflow-hidden">
          <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Communication History</p>
                <h2 className="mt-1 text-base font-semibold text-slate-950">Institution timeline summary</h2>
                <p className="mt-1 text-sm text-slate-600">Evidence-based outreach history without inferring tender status. Local timeline edits remain inside each workspace for now.</p>
              </div>
              <Link href="/outreach" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Open Outreach Center</Link>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1080px] border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                <tr>
                  <th className="border-b border-slate-200 px-5 py-3">Institution</th>
                  <th className="border-b border-slate-200 px-5 py-3">Current timeline event</th>
                  <th className="border-b border-slate-200 px-5 py-3">Outreach status</th>
                  <th className="border-b border-slate-200 px-5 py-3">Need categories</th>
                  <th className="border-b border-slate-200 px-5 py-3">Contact email</th>
                  <th className="border-b border-slate-200 px-5 py-3">Workspace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/80 bg-white">
                {activeTimelineRows.map((institution) => (
                  <tr key={institution.institution_id} className="align-top transition-colors hover:bg-slate-50/80">
                    <td className="max-w-[320px] px-5 py-4"><Link href={`/institutions/${institution.institution_id}`} className="font-medium text-slate-950 underline-offset-4 hover:text-blue-700 hover:underline">{institution.institution_display_name}</Link></td>
                    <td className="px-5 py-4"><Badge tone="info">{workflowStates[institution.institution_id]?.timeline.currentStage !== "No CRM event yet" ? workflowStates[institution.institution_id]?.timeline.currentStage : currentTimelineLabel(institution)}</Badge></td>
                    <td className="px-5 py-4"><Badge>{institution.outreach_status}</Badge></td>
                    <td className="max-w-[260px] px-5 py-4 text-sm leading-6 text-slate-600">{splitList(institution.relevant_categories).join(", ") || "Not categorized"}</td>
                    <td className="max-w-[240px] px-5 py-4 text-xs leading-5 text-slate-600">{institution.contact_email || "Not available"}</td>
                    <td className="px-5 py-4"><Link href={`/institutions/${institution.institution_id}`} className="inline-flex h-8 items-center rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Open Workspace</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
    </div>
  );
}

