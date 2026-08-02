import type { TimelineCommandResponse } from "./timeline-contract.ts";
import type { WorkflowState, WorkflowStatePatch } from "./workflow-state-types.ts";

const manualEventKeys = ["FOLLOW_UP_1", "FOLLOW_UP_2", "PHONE_CALL", "MEETING", "QUOTATION"] as const;
const derivedEventKeys = ["COLD_EMAIL_DRAFTED", "DRAFT_APPROVED", "EMAIL_SENT", "CLOSED_WON", "CLOSED_LOST"] as const;
const eventLabels: Record<(typeof manualEventKeys)[number], string> = {
  FOLLOW_UP_1: "Tindak Lanjut 1",
  FOLLOW_UP_2: "Tindak Lanjut 2",
  PHONE_CALL: "Telepon",
  MEETING: "Meeting",
  QUOTATION: "Penawaran",
};

type TimelineCommandDependencies = {
  getOperatorActor: (request: Request) => string | null;
  getWorkflowState: (institutionId: string) => WorkflowState;
  saveWorkflowState: (institutionId: string, patch: WorkflowStatePatch) => WorkflowState;
  now?: () => string;
};

function json(body: TimelineCommandResponse, status: number) {
  return Response.json(body, { status });
}

function error(status: number, code: string, message: string) {
  return json({ ok: false, error: { code, message } }, status);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, expected: readonly string[]) {
  const keys = Object.keys(value);
  return keys.length === expected.length && keys.every((key) => expected.includes(key));
}

function validateEvent(value: unknown) {
  if (typeof value !== "string") return { ok: false as const, code: "INVALID_EVENT", message: "event must be a manual timeline event identifier." };
  if (derivedEventKeys.some((key) => key === value)) {
    return { ok: false as const, code: "DERIVED_EVENT_READ_ONLY", message: "Derived outreach-status events are read-only." };
  }
  if (!manualEventKeys.some((key) => key === value)) {
    return { ok: false as const, code: "UNKNOWN_EVENT", message: "Unknown manual timeline event identifier." };
  }
  return { ok: true as const, event: value as (typeof manualEventKeys)[number] };
}

function canonicalTimeline(current: WorkflowState["timeline"]): WorkflowState["timeline"] {
  return {
    ...current,
    completedEvents: current.completedEvents.filter((event, index, values) => values.indexOf(event) === index),
    eventTimestamps: { ...current.eventTimestamps },
  };
}

export async function executeTimelineCommand(
  request: Request,
  institutionId: string,
  dependencies: TimelineCommandDependencies,
) {
  const actor = dependencies.getOperatorActor(request);
  if (!actor) return error(401, "UNAUTHORIZED", "Unauthorized.");

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return error(400, "MALFORMED_JSON", "Request body must be valid JSON.");
  }

  if (!isObject(body)) return error(400, "INVALID_COMMAND", "Request body must be an object.");
  if (body.operation !== "complete" && body.operation !== "reset") {
    return error(400, "INVALID_OPERATION", "operation must be complete or reset.");
  }
  if (!hasExactKeys(body, ["operation", "event"])) {
    return error(400, "UNKNOWN_FIELD", `${body.operation === "complete" ? "Complete" : "Reset"} accepts only operation and event.`);
  }
  const validation = validateEvent(body.event);
  if (!validation.ok) return error(400, validation.code, validation.message);

  const current = canonicalTimeline(dependencies.getWorkflowState(institutionId).timeline);
  const alreadyCompleted = current.completedEvents.includes(validation.event);
  if ((body.operation === "complete" && alreadyCompleted) || (body.operation === "reset" && !alreadyCompleted)) {
    return json({ ok: true, timeline: current }, 200);
  }

  const timestamp = (dependencies.now ?? (() => new Date().toISOString()))();
  const completedEvents = body.operation === "complete"
    ? [...current.completedEvents, validation.event]
    : current.completedEvents.filter((event) => event !== validation.event);
  const eventTimestamps = { ...current.eventTimestamps };
  if (body.operation === "complete") eventTimestamps[validation.event] = timestamp;
  else delete eventTimestamps[validation.event];
  const latestManualEvent = [...manualEventKeys].reverse().find((event) => completedEvents.includes(event));

  const state = dependencies.saveWorkflowState(institutionId, {
    timeline: {
      completedEvents,
      eventTimestamps,
      currentStage: latestManualEvent ? eventLabels[latestManualEvent] : "Belum ada aktivitas CRM",
      updatedAt: timestamp,
      updatedBy: actor,
    },
  });
  return json({ ok: true, timeline: state.timeline }, 200);
}
