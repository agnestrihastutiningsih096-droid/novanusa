import type { NextActionCommandResponse, NextActionValues } from "./next-action-contract.ts";
import type { WorkflowState, WorkflowStatePatch } from "./workflow-state-types.ts";

export const NEXT_ACTION_MAX_NOTE_LENGTH = 4_000;
const allowedActions = ["Call Again", "Send Catalog", "Send Quotation", "Waiting Response", "Schedule Meeting", "Other"] as const;

type NextActionCommandDependencies = {
  getOperatorActor: (request: Request) => string | null;
  saveWorkflowState: (institutionId: string, patch: WorkflowStatePatch) => WorkflowState;
  now?: () => string;
};

function json(body: NextActionCommandResponse, status: number) {
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

function validateNextAction(value: unknown): { ok: true; nextAction: NextActionValues } | { ok: false; code: string; message: string } {
  if (!isObject(value) || !hasExactKeys(value, ["action", "note"])) {
    return { ok: false, code: "INVALID_NEXT_ACTION_FIELDS", message: "Next Action must contain exactly action and note." };
  }
  if (typeof value.action !== "string" || !allowedActions.some((action) => action === value.action)) {
    return { ok: false, code: "INVALID_ACTION", message: `action must be one of: ${allowedActions.join(", ")}.` };
  }
  if (typeof value.note !== "string") {
    return { ok: false, code: "INVALID_NOTE", message: "note must be a string." };
  }
  if (value.note.length > NEXT_ACTION_MAX_NOTE_LENGTH) {
    return { ok: false, code: "NOTE_TOO_LONG", message: `note exceeds ${NEXT_ACTION_MAX_NOTE_LENGTH} characters.` };
  }
  return { ok: true, nextAction: { action: value.action as NextActionValues["action"], note: value.note } };
}

export async function executeNextActionCommand(
  request: Request,
  institutionId: string,
  dependencies: NextActionCommandDependencies,
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
    if (!hasExactKeys(body, ["operation", "nextAction"])) return error(400, "UNKNOWN_FIELD", "Update accepts only operation and nextAction.");
    const validation = validateNextAction(body.nextAction);
    if (!validation.ok) return error(400, validation.code, validation.message);

    const timestamp = (dependencies.now ?? (() => new Date().toISOString()))();
    const state = dependencies.saveWorkflowState(institutionId, {
      nextAction: { ...validation.nextAction, savedAt: timestamp, updatedAt: timestamp, updatedBy: actor },
    });
    return json({ ok: true, nextAction: state.nextAction }, 200);
  }

  if (body.operation === "clear") {
    if (!hasExactKeys(body, ["operation"])) return error(400, "UNKNOWN_FIELD", "Clear accepts only the operation field.");
    const timestamp = (dependencies.now ?? (() => new Date().toISOString()))();
    const state = dependencies.saveWorkflowState(institutionId, {
      nextAction: { action: allowedActions[0], note: "", savedAt: null, updatedAt: timestamp, updatedBy: actor },
    });
    return json({ ok: true, nextAction: state.nextAction }, 200);
  }

  return error(400, "INVALID_OPERATION", "operation must be update or clear.");
}
