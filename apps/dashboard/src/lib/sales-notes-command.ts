import type { SalesNotesCommandResponse, SalesNotesValues } from "./sales-notes-contract.ts";
import type { WorkflowState, WorkflowStatePatch } from "./workflow-state-types.ts";

export const SALES_NOTES_MAX_FIELD_LENGTH = 4_000;

type SalesNotesCommandDependencies = {
  getOperatorActor: (request: Request) => string | null;
  saveWorkflowState: (institutionId: string, patch: WorkflowStatePatch) => WorkflowState;
  now?: () => string;
};

const noteFields = ["contactPerson", "conversationNotes", "customerInterest", "requestedDocuments", "internalNotes"] as const;

function json(body: SalesNotesCommandResponse, status: number) {
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

function validateNotes(value: unknown): { ok: true; notes: SalesNotesValues } | { ok: false; code: string; message: string } {
  if (!isObject(value) || !hasExactKeys(value, noteFields)) {
    return { ok: false, code: "INVALID_NOTES_FIELDS", message: "Sales Notes must contain exactly the documented note fields." };
  }

  for (const field of noteFields) {
    if (typeof value[field] !== "string") {
      return { ok: false, code: "INVALID_NOTE_VALUE", message: `${field} must be a string.` };
    }
    if (value[field].length > SALES_NOTES_MAX_FIELD_LENGTH) {
      return { ok: false, code: "NOTE_TOO_LONG", message: `${field} exceeds ${SALES_NOTES_MAX_FIELD_LENGTH} characters.` };
    }
  }

  return { ok: true, notes: Object.fromEntries(noteFields.map((field) => [field, value[field]])) as SalesNotesValues };
}

export async function executeSalesNotesCommand(
  request: Request,
  institutionId: string,
  dependencies: SalesNotesCommandDependencies,
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
  if (body.operation === "update") {
    if (!hasExactKeys(body, ["operation", "notes"])) return error(400, "UNKNOWN_FIELD", "Update accepts only operation and notes.");
    const validation = validateNotes(body.notes);
    if (!validation.ok) return error(400, validation.code, validation.message);

    const timestamp = (dependencies.now ?? (() => new Date().toISOString()))();
    const state = dependencies.saveWorkflowState(institutionId, {
      salesNotes: { ...validation.notes, savedAt: timestamp, updatedAt: timestamp, updatedBy: actor },
    });
    return json({ ok: true, salesNotes: state.salesNotes }, 200);
  }

  if (body.operation === "clear") {
    if (!hasExactKeys(body, ["operation"])) return error(400, "UNKNOWN_FIELD", "Clear accepts only the operation field.");
    const timestamp = (dependencies.now ?? (() => new Date().toISOString()))();
    const state = dependencies.saveWorkflowState(institutionId, {
      salesNotes: {
        contactPerson: "",
        conversationNotes: "",
        customerInterest: "",
        requestedDocuments: "",
        internalNotes: "",
        savedAt: timestamp,
        updatedAt: timestamp,
        updatedBy: actor,
      },
    });
    return json({ ok: true, salesNotes: state.salesNotes }, 200);
  }

  return error(400, "INVALID_OPERATION", "operation must be update or clear.");
}
