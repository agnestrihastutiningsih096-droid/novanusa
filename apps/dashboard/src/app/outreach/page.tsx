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
  const underReview = institutions.filter((item) => item.outreach_status === "UNDER_REVIEW" || workflowStates[item.institution_id]?.draft.status === "UNDER_REVIEW").length;
  const approved = institutions.filter((item) => item.outreach_status === "APPROVED" || workflowStates[item.institution_id]?.draft.approved).length;
  const readyToSend = institutions.filter((item) => item.outreach_status === "READY_TO_SEND" || workflowStates[item.institution_id]?.draft.readyToSend).length;
  const sent = institutions.filter((item) => item.outreach_status === "SENT" || workflowStates[item.institution_id]?.draft.sent).length;
  const failed = institutions.filter((item) => item.outreach_status.includes("FAILED")).length;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Outreach Center"
            title="Outreach Center"
            description="Central operational view for draft, review, approval, readiness, sent, and failed outreach records across institutions. Email sending is not enabled yet."
            actions={
              <div className="flex flex-wrap gap-2">
                <Link href="/outreach/prospect-queue" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Open Prospect Queue</Link>
                <Badge tone="info">Evidence-based workflow</Badge>
              </div>
            }
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6" aria-label="Outreach Center KPIs">
          <KPI label="Drafts" value={drafts.toLocaleString("id-ID")} detail="Records with draft outreach status in the dataset." badge="Draft" href="/outreach" />
          <KPI label="Under Review" value={underReview.toLocaleString("id-ID")} detail="Records marked for draft review when available." badge="Review" href="/outreach" />
          <KPI label="Approved" value={approved.toLocaleString("id-ID")} detail="Approved records before send readiness." badge="Approve" href="/outreach" />
          <KPI label="Ready to Send" value={readyToSend.toLocaleString("id-ID")} detail="Records explicitly marked ready to send." badge="Ready" href="/outreach" />
          <KPI label="Sent" value={sent.toLocaleString("id-ID")} detail="Records marked sent in outreach status." badge="Sent" href="/crm" />
          <KPI label="Failed" value={failed.toLocaleString("id-ID")} detail="Records marked failed in outreach status." badge="Failed" href="/outreach" />
        </section>

        <Card tone="muted" className="p-4 shadow-none">
          <p className="text-sm leading-6 text-slate-600">This center uses institution outreach data and local/data-derived workflow states. Workspace draft edits are frontend-only and are not persisted globally yet. Evidence remains limited to SiRUP planning information; tender status is not inferred.</p>
        </Card>

        <OutreachCenterClient institutions={institutions} workflowStates={workflowStates} />
    </div>
  );
}


