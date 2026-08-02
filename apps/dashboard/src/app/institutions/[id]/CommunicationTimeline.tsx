"use client";

import { useEffect, useMemo, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { completedTimelineKeysFromOutreachStatus, projectEmailSent, timelineEvents, type TimelineEventKey } from "@/lib/crm-timeline";
import { fetchWorkflowStateIfActive } from "@/lib/operator-auth";
import { sendTimelineCommandIfActive } from "@/lib/timeline-client";
import { isManualTimelineEventKey, type ManualTimelineEventKey, type TimelineCommandRequest, type TimelineCommandResponse } from "@/lib/timeline-contract";
import type { WorkflowState } from "@/lib/workflow-state-types";
import { useInstitutionOperator } from "./InstitutionOperatorContext";

type CommunicationTimelineProps = {
  institutionId: string;
  outreachStatus: string;
};

type LocalTimelineEvent = {
  completed: boolean;
  derived: boolean;
  manual: boolean;
  timestamp: string | null;
};

const emptyEmailSend: WorkflowState["emailSend"] = {
  sentAt: null,
  mode: null,
  intendedRecipient: "",
  actualRecipient: "",
  subject: "",
  status: "not_sent",
  idempotencyKey: null,
  providerMessageId: null,
  error: null,
};

function formatLocalWaktu(value: string | null) {
  if (!value) {
    return "Belum dicatat";
  }

  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

async function postTimeline(institutionId: string, command: TimelineCommandRequest, operatorToken: string, operatorReady: boolean) {
  const response = await sendTimelineCommandIfActive(institutionId, operatorToken, operatorReady, command);
  if (!response) throw new Error("Token operator diperlukan");
  const payload = (await response.json()) as TimelineCommandResponse;
  if (!response.ok || !payload.ok) throw new Error(payload.ok ? "Gagal menyimpan timeline" : payload.error.message);
  return payload.timeline;
}

function mergeTimeline(timeline: WorkflowState["timeline"], emailSend: WorkflowState["emailSend"], derivedEvents: Set<TimelineEventKey>) {
  const manualEvents = new Set(timeline.completedEvents);
  const emailSent = projectEmailSent(emailSend);
  return Object.fromEntries(
    timelineEvents.map((event) => {
      const derived = event.key === "EMAIL_SENT" ? emailSent.completed : derivedEvents.has(event.key);
      const manual = isManualTimelineEventKey(event.key) && manualEvents.has(event.key);
      const timestamp = event.key === "EMAIL_SENT" ? emailSent.timestamp : manual ? timeline.eventTimestamps[event.key] ?? null : null;
      return [event.key, { completed: derived || manual, derived, manual, timestamp }];
    }),
  ) as Record<TimelineEventKey, LocalTimelineEvent>;
}

export default function CommunicationTimeline({ institutionId, outreachStatus }: CommunicationTimelineProps) {
  const { operatorReady, operatorToken } = useInstitutionOperator();
  const initialCompleted = useMemo(() => completedTimelineKeysFromOutreachStatus(outreachStatus), [outreachStatus]);
  const [aktivitas, setEvents] = useState<Record<TimelineEventKey, LocalTimelineEvent>>(() => {
    return mergeTimeline(
      { completedEvents: [], eventTimestamps: {}, currentStage: "No CRM event yet", updatedAt: null, updatedBy: null },
      emptyEmailSend,
      initialCompleted,
    );
  });
  const [emailSend, setEmailSend] = useState<WorkflowState["emailSend"]>(emptyEmailSend);
  const [message, setMessage] = useState("Memuat");

  useEffect(() => {
    if (!operatorReady || !operatorToken) return;
    let active = true;

    fetchWorkflowStateIfActive(institutionId, operatorToken, operatorReady)!
      .then((response) => response.json() as Promise<WorkflowState>)
      .then((state) => {
        if (!active) return;
        setEmailSend(state.emailSend);
        setEvents(mergeTimeline(state.timeline, state.emailSend, initialCompleted));
        setMessage(state.timeline.updatedAt ? "Timeline tersimpan dimuat" : "Belum ada timeline tersimpan");
      })
      .catch(() => {
        if (active) setMessage("Timeline tidak dapat dimuat");
      });

    return () => {
      active = false;
    };
  }, [initialCompleted, institutionId, operatorReady, operatorToken]);

  const completedCount = timelineEvents.filter((event) => aktivitas[event.key].completed).length;

  async function markComplete(event: ManualTimelineEventKey) {
    const timeline = await postTimeline(institutionId, { operation: "complete", event }, operatorToken, operatorReady);
    setEvents(mergeTimeline(timeline, emailSend, initialCompleted));
    setMessage("Tersimpan ke backend");
  }

  async function resetEvent(event: ManualTimelineEventKey) {
    const timeline = await postTimeline(institutionId, { operation: "reset", event }, operatorToken, operatorReady);
    setEvents(mergeTimeline(timeline, emailSend, initialCompleted));
    setMessage("Tersimpan ke backend");
  }

  return (
    <Card className="p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Timeline CRM</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Institusi communication timeline</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Catat aktivitas komunikasi tersimpan untuk institusi ini. Pengiriman email tetap mengikuti workflow terkontrol.</p>
        </div>
        <Badge tone={completedCount > 0 ? "info" : "neutral"}>{completedCount.toLocaleString("id-ID")} / {timelineEvents.length.toLocaleString("id-ID")} aktivitas</Badge>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {timelineEvents.map((event, index) => {
          const state = aktivitas[event.key];
          const manualEvent = isManualTimelineEventKey(event.key) ? event.key : null;

          return (
            <div key={event.key} className="rounded-md border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Langkah {(index + 1).toLocaleString("id-ID")}</p>
                  <h3 className="mt-2 text-sm font-semibold text-slate-950">{event.label}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{event.description}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Badge tone={state.completed ? "success" : "neutral"}>{state.completed ? "Tercatat" : "Menunggu"}</Badge>
                  <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">{state.derived ? "Proyeksi outreach" : "Overlay manual"}</span>
                </div>
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-500">Waktu: {formatLocalWaktu(state.timestamp)}</p>
              {manualEvent ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={() => markComplete(manualEvent)} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Tandai Selesai</button>
                  <button type="button" onClick={() => resetEvent(manualEvent)} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Reset</button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-xs leading-5 text-slate-500">{operatorReady ? message : "Token operator diperlukan"}. Aktivitas timeline tidak menyimpulkan status tender.</p>
    </Card>
  );
}
