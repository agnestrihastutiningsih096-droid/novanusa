import fs from "node:fs";
import path from "node:path";
import type { CommunicationOutcomeAppend, CommunicationOutcomeAppendResult, CommunicationOutcomePriorCommand } from "./communication-outcome.ts";

type StoreFile = {
  outcomes: CommunicationOutcomeAppend["record"][];
  audits: CommunicationOutcomeAppend["audit"][];
  commands: Record<string, { canonicalContent: string; outcomeId: string; auditEventId: string }>;
};

const storePath = process.env.NOVANUSA_COMMUNICATION_OUTCOMES_PATH
  ? path.resolve(process.env.NOVANUSA_COMMUNICATION_OUTCOMES_PATH)
  : path.resolve(process.cwd(), "..", "..", "data", "dashboard_communication_outcomes.json");

function emptyStore(): StoreFile {
  return { outcomes: [], audits: [], commands: {} };
}

function readStore(): StoreFile {
  if (!fs.existsSync(storePath)) return emptyStore();
  const parsed = JSON.parse(fs.readFileSync(storePath, "utf8")) as StoreFile;
  if (!Array.isArray(parsed.outcomes) || !Array.isArray(parsed.audits) || !parsed.commands || typeof parsed.commands !== "object") {
    throw new Error("Invalid communication outcome store");
  }
  return parsed;
}

function writeStore(store: StoreFile) {
  fs.mkdirSync(path.dirname(storePath), { recursive: true });
  const tempPath = `${storePath}.${process.pid}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(store, null, 2), "utf8");
  fs.renameSync(tempPath, storePath);
}

export function appendCommunicationOutcome(append: CommunicationOutcomeAppend): CommunicationOutcomeAppendResult {
  const store = readStore();
  const previous = store.commands[append.commandId];
  if (previous) {
    if (previous.canonicalContent !== append.canonicalContent) return { status: "conflict" };
    const record = store.outcomes.find((item) => item.id === previous.outcomeId);
    const audit = store.audits.find((item) => item.eventId === previous.auditEventId);
    if (!record || !audit) throw new Error("Incomplete communication outcome command");
    return { status: "replayed", result: { data: record, audit: { eventId: audit.eventId } } };
  }

  const next: StoreFile = {
    outcomes: [...store.outcomes, append.record],
    audits: [...store.audits, append.audit],
    commands: {
      ...store.commands,
      [append.commandId]: {
        canonicalContent: append.canonicalContent,
        outcomeId: append.record.id,
        auditEventId: append.audit.eventId,
      },
    },
  };
  writeStore(next);
  return { status: "created", result: { data: append.record, audit: { eventId: append.audit.eventId } } };
}

export function getCommunicationOutcomeCommand(commandId: string): CommunicationOutcomePriorCommand | null {
  const store = readStore();
  const command = store.commands[commandId];
  if (!command) return null;
  const record = store.outcomes.find((item) => item.id === command.outcomeId);
  const audit = store.audits.find((item) => item.eventId === command.auditEventId);
  if (!record || !audit) throw new Error("Incomplete communication outcome command");
  return { canonicalContent: command.canonicalContent, result: { data: record, audit: { eventId: audit.eventId } } };
}

export function findLatestGenericCommunicationOutcome(
  outcomes: CommunicationOutcomeAppend["record"][],
  institutionId: string,
) {
  return outcomes.findLast((record) => record.institutionId === institutionId && record.procurementIdentityId === null) ?? null;
}

export function getLatestGenericCommunicationOutcome(institutionId: string) {
  return findLatestGenericCommunicationOutcome(readStore().outcomes, institutionId);
}

export function getCommunicationOutcomeStorePath() {
  return storePath;
}
