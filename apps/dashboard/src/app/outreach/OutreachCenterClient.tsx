"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { splitList, type Prospect } from "@/lib/institution-utils";
import type { WorkflowState } from "@/lib/workflow-state-types";

type OutreachStage = "Drafts" | "Under Review" | "Approved" | "Ready to Send" | "Sent" | "Failed";

type OutreachCenterClientProps = {
  institutions: Prospect[];
  workflowStates: Record<string, WorkflowState>;
};

const stages: OutreachStage[] = ["Drafts", "Under Review", "Approved", "Ready to Send", "Sent", "Failed"];

function stageFor(item: Prospect, workflowState?: WorkflowState): OutreachStage | null {
  if (workflowState?.draft.sent) {
    return "Sent";
  }
  if (workflowState?.draft.readyToSend) {
    return "Ready to Send";
  }
  if (workflowState?.draft.approved) {
    return "Approved";
  }
  if (workflowState?.draft.status === "UNDER_REVIEW") {
    return "Under Review";
  }
  if (["GENERATED", "EDITED", "SAVED"].includes(workflowState?.draft.status ?? "")) {
    return "Drafts";
  }

  const status = item.outreach_status.toUpperCase();

  if (status.includes("FAILED")) {
    return "Failed";
  }
  if (status === "SENT") {
    return "Sent";
  }
  if (status === "READY_TO_SEND") {
    return "Ready to Send";
  }
  if (status === "APPROVED") {
    return "Approved";
  }
  if (status === "UNDER_REVIEW") {
    return "Under Review";
  }
  if (status.includes("DRAFT")) {
    return "Drafts";
  }

  return null;
}

function draftReviewStatus(item: Prospect, workflowState?: WorkflowState) {
  const stage = stageFor(item, workflowState);

  if (stage) {
    return stage;
  }
  if (item.outreach_status === "NOT_CONTACTED") {
    return "Not Generated";
  }
  return item.outreach_status || "Not Available";
}

function toneForStage(stage: string) {
  if (["Approved", "Ready to Send", "Sent"].includes(stage)) {
    return "success";
  }
  if (stage === "Under Review") {
    return "warning";
  }
  if (stage === "Failed") {
    return "warning";
  }
  if (stage === "Not Generated") {
    return "neutral";
  }
  return "info";
}

export default function OutreachCenterClient({ institutions, workflowStates }: OutreachCenterClientProps) {
  const [activeStage, setActiveStage] = useState<OutreachStage>("Drafts");

  const counts = useMemo(() => {
    return Object.fromEntries(stages.map((stage) => [stage, institutions.filter((item) => stageFor(item, workflowStates[item.institution_id]) === stage).length])) as Record<OutreachStage, number>;
  }, [institutions, workflowStates]);

  const activeRows = useMemo(() => {
    return institutions.filter((item) => stageFor(item, workflowStates[item.institution_id]) === activeStage).slice(0, 50);
  }, [activeStage, institutions, workflowStates]);

  return (
    <>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6" aria-label="Outreach workflow stages">
        {stages.map((stage) => (
          <button
            key={stage}
            type="button"
            onClick={() => setActiveStage(stage)}
            className={`rounded-lg border p-4 text-left transition ${activeStage === stage ? "border-blue-200 bg-blue-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">{stage}</p>
            <p className="mt-3 text-2xl font-semibold text-slate-950">{counts[stage].toLocaleString("id-ID")}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">Data-derived outreach records</p>
          </button>
        ))}
      </section>

      <Card className="overflow-hidden">
        <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{activeStage}</p>
              <h2 className="mt-1 text-base font-semibold text-slate-950">{activeRows.length.toLocaleString("id-ID")} records shown</h2>
              <p className="mt-1 text-sm text-slate-600">Draft review status is shown when it exists in the outreach data. Persisted draft and send status are reflected when available.</p>
            </div>
            <Badge tone="info">Local / data-derived</Badge>
          </div>
        </div>

        {activeRows.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1180px] border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                <tr>
                  <th className="border-b border-slate-200 px-5 py-3">Institution</th>
                  <th className="border-b border-slate-200 px-5 py-3">Contact email</th>
                  <th className="border-b border-slate-200 px-5 py-3">Target level</th>
                  <th className="border-b border-slate-200 px-5 py-3">Need categories</th>
                  <th className="border-b border-slate-200 px-5 py-3">Outreach status</th>
                  <th className="border-b border-slate-200 px-5 py-3">Draft / review status</th>
                  <th className="border-b border-slate-200 px-5 py-3">Send status</th>
                  <th className="border-b border-slate-200 px-5 py-3">Workspace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/80 bg-white">
                {activeRows.map((item) => {
                  const reviewStatus = draftReviewStatus(item, workflowStates[item.institution_id]);

                  return (
                    <tr key={item.institution_id} className="align-top transition-colors hover:bg-slate-50/80">
                      <td className="max-w-[320px] px-5 py-4">
                        <Link href={`/institutions/${item.institution_id}`} className="font-medium text-slate-950 underline-offset-4 hover:text-blue-700 hover:underline">
                          {item.institution_display_name}
                        </Link>
                        <p className="mt-1 text-xs leading-5 text-slate-500">{item.institution_name}</p>
                      </td>
                      <td className="max-w-[240px] px-5 py-4 text-xs leading-5 text-slate-600">{item.contact_email || "Not available"}</td>
                      <td className="px-5 py-4"><Badge>{item.target_level || "Not available"}</Badge></td>
                      <td className="max-w-[260px] px-5 py-4 text-sm leading-6 text-slate-600">{splitList(item.relevant_categories).join(", ") || "Not categorized"}</td>
                      <td className="px-5 py-4"><Badge>{item.outreach_status || "Not available"}</Badge></td>
                      <td className="px-5 py-4"><Badge tone={toneForStage(reviewStatus)}>{reviewStatus}</Badge></td>
                      <td className="px-5 py-4"><Badge tone={workflowStates[item.institution_id]?.emailSend.status === "sent" ? "success" : workflowStates[item.institution_id]?.emailSend.status === "failed" ? "warning" : "neutral"}>{workflowStates[item.institution_id]?.emailSend.status ?? "not_sent"}</Badge></td>
                      <td className="px-5 py-4">
                        <Link href={`/institutions/${item.institution_id}`} className="inline-flex h-8 items-center rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Open Workspace</Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-10 md:px-6">
            <Card tone="muted" className="p-5 shadow-none">
              <h3 className="text-sm font-semibold text-slate-950">No records in {activeStage}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">No institution records currently have this outreach state in the loaded dataset. Use the Institution Workspace to generate, review, and approve drafts locally.</p>
            </Card>
          </div>
        )}
      </Card>
    </>
  );
}


