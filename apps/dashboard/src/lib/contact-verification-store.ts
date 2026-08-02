import fs from "node:fs";
import path from "node:path";
import type { ContactVerificationRecord } from "./contact-verification.ts";

type ContactVerificationFile = Record<string, ContactVerificationRecord>;

const contactVerificationPath = process.env.NOVANUSA_CONTACT_VERIFICATIONS_PATH
  ? path.resolve(process.env.NOVANUSA_CONTACT_VERIFICATIONS_PATH)
  : path.resolve(process.cwd(), "..", "..", "data", "dashboard_contact_verifications.json");

function readStore(): ContactVerificationFile {
  if (!fs.existsSync(contactVerificationPath)) return {};
  try {
    const parsed = JSON.parse(fs.readFileSync(contactVerificationPath, "utf8")) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as ContactVerificationFile : {};
  } catch {
    return {};
  }
}

function writeStore(store: ContactVerificationFile) {
  fs.mkdirSync(path.dirname(contactVerificationPath), { recursive: true });
  const tempPath = `${contactVerificationPath}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(store, null, 2), "utf8");
  fs.renameSync(tempPath, contactVerificationPath);
}

export function getContactVerification(institutionId: string) {
  return readStore()[institutionId] ?? null;
}

export function saveContactVerification(record: ContactVerificationRecord) {
  const store = readStore();
  const existing = store[record.institutionId];
  if (existing?.evidenceFingerprint === record.evidenceFingerprint) return existing;
  store[record.institutionId] = record;
  writeStore(store);
  return record;
}

export function getContactVerificationPath() {
  return contactVerificationPath;
}
