import type { TimelineEventKey } from "./crm-timeline";
import type { WorkflowState } from "./workflow-state-types.ts";

export const MANUAL_TIMELINE_EVENT_KEYS = ["FOLLOW_UP_1", "FOLLOW_UP_2", "PHONE_CALL", "MEETING", "QUOTATION"] as const;
export const DERIVED_TIMELINE_EVENT_KEYS = ["COLD_EMAIL_DRAFTED", "DRAFT_APPROVED", "EMAIL_SENT", "CLOSED_WON", "CLOSED_LOST"] as const;

export type ManualTimelineEventKey = (typeof MANUAL_TIMELINE_EVENT_KEYS)[number];

export function isManualTimelineEventKey(key: TimelineEventKey): key is ManualTimelineEventKey {
  return MANUAL_TIMELINE_EVENT_KEYS.some((manualKey) => manualKey === key);
}

export type TimelineCommandRequest =
  | { operation: "complete"; event: ManualTimelineEventKey }
  | { operation: "reset"; event: ManualTimelineEventKey };

export type TimelineCommandResponse =
  | { ok: true; timeline: WorkflowState["timeline"] }
  | { ok: false; error: { code: string; message: string } };
