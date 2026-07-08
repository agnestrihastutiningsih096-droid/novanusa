import type { Prospect } from "@/lib/institution-utils";

export type TimelineEventKey =
  | "COLD_EMAIL_DRAFTED"
  | "DRAFT_APPROVED"
  | "EMAIL_SENT"
  | "FOLLOW_UP_1"
  | "FOLLOW_UP_2"
  | "PHONE_CALL"
  | "MEETING"
  | "QUOTATION"
  | "CLOSED_WON"
  | "CLOSED_LOST";

export type TimelineEventDefinition = {
  key: TimelineEventKey;
  label: string;
  description: string;
};

export const timelineEvents: TimelineEventDefinition[] = [
  { key: "COLD_EMAIL_DRAFTED", label: "Cold Email Drafted", description: "Evidence-based cold outreach draft prepared locally." },
  { key: "DRAFT_APPROVED", label: "Draft Approved", description: "Draft reviewed and approved before any send step." },
  { key: "EMAIL_SENT", label: "Email Sent", description: "Placeholder state only. No real email is sent yet." },
  { key: "FOLLOW_UP_1", label: "Follow-up 1", description: "First follow-up activity after the send placeholder." },
  { key: "FOLLOW_UP_2", label: "Follow-up 2", description: "Second follow-up activity after initial follow-up." },
  { key: "PHONE_CALL", label: "Phone Call", description: "Phone communication recorded locally." },
  { key: "MEETING", label: "Meeting", description: "Meeting activity recorded locally." },
  { key: "QUOTATION", label: "Quotation", description: "Quotation activity recorded locally." },
  { key: "CLOSED_WON", label: "Closed Won", description: "Institution communication outcome marked locally as won." },
  { key: "CLOSED_LOST", label: "Closed Lost", description: "Institution communication outcome marked locally as lost." },
];

export function completedTimelineKeysFromOutreachStatus(status: string): Set<TimelineEventKey> {
  const normalized = status.toUpperCase();
  const completed = new Set<TimelineEventKey>();

  if (normalized.includes("DRAFT") || normalized === "UNDER_REVIEW" || normalized === "APPROVED" || normalized === "READY_TO_SEND" || normalized === "SENT") {
    completed.add("COLD_EMAIL_DRAFTED");
  }
  if (normalized === "APPROVED" || normalized === "READY_TO_SEND" || normalized === "SENT") {
    completed.add("DRAFT_APPROVED");
  }
  if (normalized === "SENT") {
    completed.add("EMAIL_SENT");
  }
  if (normalized === "CLOSED_WON") {
    completed.add("COLD_EMAIL_DRAFTED");
    completed.add("DRAFT_APPROVED");
    completed.add("EMAIL_SENT");
    completed.add("CLOSED_WON");
  }
  if (normalized === "CLOSED_LOST") {
    completed.add("COLD_EMAIL_DRAFTED");
    completed.add("DRAFT_APPROVED");
    completed.add("EMAIL_SENT");
    completed.add("CLOSED_LOST");
  }

  return completed;
}

export function currentTimelineLabel(prospect: Prospect) {
  const completed = completedTimelineKeysFromOutreachStatus(prospect.outreach_status);
  const latest = [...timelineEvents].reverse().find((event) => completed.has(event.key));

  return latest?.label ?? "No CRM event yet";
}

