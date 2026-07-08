"use client";

import { useEffect, useMemo, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { completedTimelineKeysFromOutreachStatus, timelineEvents, type TimelineEventKey } from "@/lib/crm-timeline";
import type { WorkflowState, WorkflowStatePatch } from "@/lib/workflow-state-types";

type CommunicationTimelineProps = {
  institutionId: string;
  outreachStatus: string;
};

type LocalTimelineEvent = {
  completed: boolean;
  timestamp: string | null;
};

function formatLocalTimestamp(value: string | null) {
  if (!value) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

async function postWorkflowState(institutionId: string, patch: WorkflowStatePatch) {
  const response = await fetch(`/api/institutions/${encodeURIComponent(institutionId)}/workflow-state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });

  if (!response.ok) {
    throw new Error("Failed to save workflow state");
  }

  return (await response.json()) as WorkflowState;
}

function labelForKey(key: TimelineEventKey) {
  return timelineEvents.find((event) => event.key === key)?.label ?? "No CRM event yet";
}

export default function CommunicationTimeline({ institutionId, outreachStatus }: CommunicationTimelineProps) {
  const initialCompleted = useMemo(() => completedTimelineKeysFromOutreachStatus(outreachStatus), [outreachStatus]);
  const [events, setEvents] = useState<Record<TimelineEventKey, LocalTimelineEvent>>(() => {
    return Object.fromEntries(timelineEvents.map((event) => [event.key, { completed: initialCompleted.has(event.key), timestamp: null }])) as Record<TimelineEventKey, LocalTimelineEvent>;
  });
  const [message, setMessage] = useState("Load pending");

  useEffect(() => {
    let active = true;

    fetch(`/api/institutions/${encodeURIComponent(institutionId)}/workflow-state`)
      .then((response) => response.json() as Promise<WorkflowState>)
      .then((state) => {
        if (!active) return;
        const completed = new Set<TimelineEventKey>([...Array.from(initialCompleted), ...state.timeline.completedEvents]);
        const next = Object.fromEntries(
          timelineEvents.map((event) => [
            event.key,
            {
              completed: completed.has(event.key),
              timestamp: state.timeline.eventTimestamps[event.key] ?? null,
            },
          ]),
        ) as Record<TimelineEventKey, LocalTimelineEvent>;
        setEvents(next);
        setMessage(state.timeline.updatedAt ? "Loaded saved timeline" : "No saved timeline yet");
      })
      .catch(() => {
        if (active) setMessage("Could not load timeline");
      });

    return () => {
      active = false;
    };
  }, [initialCompleted, institutionId]);

  const completedCount = timelineEvents.filter((event) => events[event.key].completed).length;

  async function persist(nextEvents: Record<TimelineEventKey, LocalTimelineEvent>) {
    const completedEvents = timelineEvents.filter((event) => nextEvents[event.key].completed).map((event) => event.key);
    const eventTimestamps = Object.fromEntries(timelineEvents.map((event) => [event.key, nextEvents[event.key].timestamp]).filter(([, value]) => Boolean(value)));
    const currentStage = completedEvents.length > 0 ? labelForKey(completedEvents[completedEvents.length - 1]) : "No CRM event yet";

    await postWorkflowState(institutionId, {
      timeline: {
        completedEvents,
        eventTimestamps,
        currentStage,
        updatedAt: new Date().toISOString(),
      },
    });
    setMessage("Saved to backend");
  }

  async function markComplete(key: TimelineEventKey) {
    const next = {
      ...events,
      [key]: { completed: true, timestamp: new Date().toISOString() },
    };
    setEvents(next);
    await persist(next);
  }

  async function resetEvent(key: TimelineEventKey) {
    const next = {
      ...events,
      [key]: { completed: false, timestamp: null },
    };
    setEvents(next);
    await persist(next);
  }

  return (
    <Card className="p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">CRM Timeline</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Institution communication timeline</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Track persisted communication events for this institution. No real email sending yet.</p>
        </div>
        <Badge tone={completedCount > 0 ? "info" : "neutral"}>{completedCount.toLocaleString("id-ID")} / {timelineEvents.length.toLocaleString("id-ID")} events</Badge>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {timelineEvents.map((event, index) => {
          const state = events[event.key];

          return (
            <div key={event.key} className="rounded-md border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Step {(index + 1).toLocaleString("id-ID")}</p>
                  <h3 className="mt-2 text-sm font-semibold text-slate-950">{event.label}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{event.description}</p>
                </div>
                <Badge tone={state.completed ? "success" : "neutral"}>{state.completed ? "Recorded" : "Pending"}</Badge>
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-500">Timestamp: {formatLocalTimestamp(state.timestamp)}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" onClick={() => markComplete(event.key)} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Mark Complete</button>
                <button type="button" onClick={() => resetEvent(event.key)} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Reset</button>
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-xs leading-5 text-slate-500">{message}. Timeline entries do not infer tender status.</p>
    </Card>
  );
}
