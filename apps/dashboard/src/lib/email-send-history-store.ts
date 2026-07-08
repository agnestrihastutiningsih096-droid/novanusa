import fs from "fs";
import path from "path";
import type { EmailSendMode } from "@/lib/workflow-state-types";

export type EmailSendHistoryRecord = {
  institutionId: string;
  sentAt: string;
  mode: EmailSendMode;
  intendedRecipient: string;
  actualRecipient: string;
  subject: string;
  providerMessageId: string | null;
  status: "sent" | "failed";
  error: string | null;
};

const sendHistoryPath = path.resolve(process.cwd(), "..", "..", "data", "dashboard_email_send_history.json");

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
