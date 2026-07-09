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
  { key: "COLD_EMAIL_DRAFTED", label: "Draf Email Dibuat", description: "Draf outreach berbasis bukti disiapkan secara lokal." },
  { key: "DRAFT_APPROVED", label: "Draf Disetujui", description: "Draf ditinjau dan disetujui sebelum tahap pengiriman." },
  { key: "EMAIL_SENT", label: "Email Terkirim", description: "Status pengiriman yang dicatat oleh workflow terkontrol." },
  { key: "FOLLOW_UP_1", label: "Tindak Lanjut 1", description: "Aktivitas tindak lanjut pertama setelah pengiriman." },
  { key: "FOLLOW_UP_2", label: "Tindak Lanjut 2", description: "Aktivitas tindak lanjut kedua setelah tindak lanjut awal." },
  { key: "PHONE_CALL", label: "Telepon", description: "Komunikasi telepon dicatat secara lokal." },
  { key: "MEETING", label: "Meeting", description: "Aktivitas meeting dicatat secara lokal." },
  { key: "QUOTATION", label: "Penawaran", description: "Aktivitas penawaran dicatat secara lokal." },
  { key: "CLOSED_WON", label: "Menang", description: "Hasil komunikasi dengan institusi ditandai menang secara lokal." },
  { key: "CLOSED_LOST", label: "Kalah", description: "Hasil komunikasi dengan institusi ditandai kalah secara lokal." },
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

  return latest?.label ?? "Belum ada aktivitas CRM";
}

