import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";
import type { EmailSendMode } from "@/lib/workflow-state-types";
import type { ContactVerificationSnapshot } from "@/lib/institution-data";

export type EmailSendHistoryRecord = {
  institutionId: string;
  sentAt: string;
  mode: EmailSendMode;
  intendedRecipient: string;
  actualRecipient: string;
  subject: string;
  providerMessageId: string | null;
  status: "reserved" | "sent" | "failed";
  error: string | null;
  actor?: string;
  approvalActor?: string | null;
  approvalTimestamp?: string | null;
  contactVerification?: ContactVerificationSnapshot;
  idempotencyKey?: string;
  provider?: "resend" | "mock";
  result?: "SEND_RESERVED" | "SENT" | "FAILED";
  safeErrorCode?: string | null;
  attemptTimestamp?: string;
  attemptId?: string;
  attemptNumber?: number;
};

const sendHistoryPath = process.env.NOVANUSA_EMAIL_HISTORY_PATH
  ? path.resolve(process.env.NOVANUSA_EMAIL_HISTORY_PATH)
  : path.resolve(process.cwd(), "..", "..", "data", "dashboard_email_send_history.json");

function ensureStoreDirectory() {
  fs.mkdirSync(path.dirname(sendHistoryPath), { recursive: true });
}

function readHistory(): EmailSendHistoryRecord[] {
  ensureStoreDirectory();

  if (!fs.existsSync(sendHistoryPath)) {
    return [];
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(sendHistoryPath, "utf8")) as EmailSendHistoryRecord[] | EmailSendHistoryRecord;
    return Array.isArray(parsed) ? parsed : [parsed];
  } catch {
    return [];
  }
}

export function getEmailSendHistory() {
  return readHistory();
}

function writeHistory(records: EmailSendHistoryRecord[]) {
  ensureStoreDirectory();
  const tempPath = `${sendHistoryPath}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(records, null, 2), "utf8");
  fs.renameSync(tempPath, sendHistoryPath);
}

export function getEmailSendHistoryPath() {
  return sendHistoryPath;
}

export function appendEmailSendHistory(record: EmailSendHistoryRecord) {
  const records = readHistory();
  records.push(record);
  writeHistory(records);
  return record;
}

export type ReservationResult =
  | { acquired: true; record: EmailSendHistoryRecord }
  | { acquired: false; existing: EmailSendHistoryRecord | null };

const processReservations = new Set<string>();

export function reserveEmailSend(record: EmailSendHistoryRecord): ReservationResult {
  const key = record.idempotencyKey;
  if (!key) throw new Error("Reservation requires an idempotency key.");

  if (processReservations.has(key)) {
    return { acquired: false, existing: readHistory().find((item) => item.idempotencyKey === key) ?? null };
  }

  processReservations.add(key);
  try {
    const records = readHistory();
    const attempts = records.filter((item) => item.idempotencyKey === key);
    const blockingAttempt = attempts.find((item) => item.status === "sent" || item.status === "reserved");
    if (blockingAttempt) return { acquired: false, existing: blockingAttempt };
    const attemptNumber = attempts.reduce((maximum, item, index) => Math.max(maximum, item.attemptNumber ?? index + 1), 0) + 1;
    const reservedRecord = { ...record, attemptId: randomUUID(), attemptNumber };
    records.push(reservedRecord);
    writeHistory(records);
    return { acquired: true, record: reservedRecord };
  } finally {
    processReservations.delete(key);
  }
}

export function finalizeEmailSend(attemptId: string, patch: Partial<EmailSendHistoryRecord>) {
  const records = readHistory();
  const index = records.findIndex((item) => item.attemptId === attemptId);
  if (index < 0) throw new Error("Email reservation was not found.");
  records[index] = { ...records[index], ...patch };
  writeHistory(records);
  return records[index];
}
