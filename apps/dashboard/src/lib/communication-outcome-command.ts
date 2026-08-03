import { randomUUID } from "node:crypto";
import {
  COMMUNICATION_OUTCOMES,
  type CommunicationOutcome,
  type CommunicationOutcomeAppend,
  type CommunicationOutcomeAppendResult,
  type CommunicationOutcomePriorCommand,
  type CommunicationOutcomeRecord,
} from "./communication-outcome.ts";

type Dependencies = {
  getOperatorActor: (request: Request) => string | null;
  institutionExists: (institutionId: string) => boolean;
  procurementIdentityBelongsToInstitution: (institutionId: string, procurementIdentityId: string) => boolean;
  getCommand: (commandId: string) => CommunicationOutcomePriorCommand | null;
  append: (value: CommunicationOutcomeAppend) => CommunicationOutcomeAppendResult;
  now?: () => string;
  createId?: () => string;
};

const message = "Communication outcome could not be recorded.";

function error(status: number, code: string, fields?: string[]) {
  return Response.json(
    { error: { code, message, ...(fields ? { details: { fields } } : {}) } },
    { status },
  );
}

type ReadDependencies = {
  getOperatorActor: (request: Request) => string | null;
  institutionExists: (institutionId: string) => boolean;
  getLatestGeneric: (institutionId: string) => CommunicationOutcomeRecord | null;
};

export function executeCommunicationOutcomeRead(request: Request, institutionId: string, dependencies: ReadDependencies) {
  if (!dependencies.getOperatorActor(request)) return error(401, "UNAUTHORIZED");
  if (!dependencies.institutionExists(institutionId)) return error(404, "INSTITUTION_NOT_FOUND");
  try {
    return Response.json({ data: dependencies.getLatestGeneric(institutionId) });
  } catch {
    return error(500, "PERSISTENCE_FAILED");
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function executeCommunicationOutcomeCommand(request: Request, institutionId: string, dependencies: Dependencies) {
  const actor = dependencies.getOperatorActor(request);
  if (!actor) return error(401, "UNAUTHORIZED");
  if (!dependencies.institutionExists(institutionId)) return error(404, "INSTITUTION_NOT_FOUND");

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return error(400, "INVALID_JSON");
  }

  if (!isObject(body)) return error(400, "VALIDATION_FAILED", []);
  const allowed = ["commandId", "outcome", "procurementIdentityId", "note"];
  const invalidFields = Object.keys(body).filter((key) => !allowed.includes(key));
  if (!("commandId" in body)) invalidFields.push("commandId");
  if (!("outcome" in body)) invalidFields.push("outcome");
  if (typeof body.commandId !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(body.commandId)) invalidFields.push("commandId");
  if (typeof body.outcome !== "string" || !COMMUNICATION_OUTCOMES.includes(body.outcome as CommunicationOutcome)) invalidFields.push("outcome");
  if ("procurementIdentityId" in body && (typeof body.procurementIdentityId !== "string" || !body.procurementIdentityId.trim() || body.procurementIdentityId !== body.procurementIdentityId.trim())) invalidFields.push("procurementIdentityId");
  if ("note" in body && (typeof body.note !== "string" || !body.note.trim() || body.note.trim().length > 2_000)) invalidFields.push("note");
  const fields = [...new Set(invalidFields)].sort();
  if (fields.length) return error(400, "VALIDATION_FAILED", fields);

  const commandId = body.commandId as string;
  const outcome = body.outcome as CommunicationOutcome;
  const procurementIdentityId = body.procurementIdentityId as string | undefined;
  const note = typeof body.note === "string" ? body.note.trim() : null;
  const canonicalContent = JSON.stringify({ institutionId, procurementIdentityId: procurementIdentityId ?? null, outcome, note });
  try {
    const prior = dependencies.getCommand(commandId);
    if (prior) {
      if (prior.canonicalContent !== canonicalContent) return error(409, "COMMAND_ID_REUSED");
      return Response.json(prior.result, { status: 200 });
    }
  } catch {
    return error(500, "PERSISTENCE_FAILED");
  }
  if (procurementIdentityId && !dependencies.procurementIdentityBelongsToInstitution(institutionId, procurementIdentityId)) {
    return error(404, "PROCUREMENT_IDENTITY_NOT_FOUND");
  }

  const recordedAt = (dependencies.now ?? (() => new Date().toISOString()))();
  const createId = dependencies.createId ?? randomUUID;
  const recordId = createId();
  const auditEventId = createId();
  try {
    const saved = dependencies.append({
      commandId,
      canonicalContent,
      record: { id: recordId, institutionId, procurementIdentityId: procurementIdentityId ?? null, outcome, note, actor, recordedAt },
      audit: { eventId: auditEventId, commandId, actor, recordedAt, action: "communication_outcome.recorded", institutionId, procurementIdentityId: procurementIdentityId ?? null, outcomeId: recordId },
    });
    if (saved.status === "conflict") return error(409, "COMMAND_ID_REUSED");
    return Response.json(saved.result, { status: saved.status === "created" ? 201 : 200 });
  } catch {
    return error(500, "PERSISTENCE_FAILED");
  }
}
