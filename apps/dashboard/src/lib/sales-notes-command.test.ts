/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { getOperatorActor } from "./email-sender.ts";
import { executeSalesNotesCommand, SALES_NOTES_MAX_FIELD_LENGTH } from "./sales-notes-command.ts";
import { createDefaultWorkflowState } from "./workflow-state-types.ts";

const validToken = "valid-sales-notes-token";
const fixedTimestamp = "2026-08-01T12:00:00.000Z";
const validNotes = {
  contactPerson: "Bapak Andi",
  conversationNotes: "Memerlukan katalog terbaru.\nTindak lanjut minggu depan.",
  customerInterest: "Laptop",
  requestedDocuments: "Katalog",
  internalNotes: "Prioritas sedang",
};

function commandRequest(body: unknown, token?: string) {
  return new Request("http://localhost/api/institutions/inst-1/sales-notes", {
    method: "POST",
    headers: token ? { "Content-Type": "application/json", "x-novanusa-operator-token": token } : { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function fixture() {
  let state = createDefaultWorkflowState();
  state = {
    ...state,
    draft: { ...state.draft, text: "Existing draft", status: "SAVED" },
    nextAction: { action: "Schedule Meeting", note: "Existing action", savedAt: "old-action-time" },
    timeline: { completedEvents: ["PHONE_CALL"], eventTimestamps: { PHONE_CALL: "old-timeline-time" }, currentStage: "Telepon", updatedAt: "old-timeline-time" },
    emailSend: { ...state.emailSend, intendedRecipient: "institution@example.go.id" },
  };
  const before = structuredClone(state);
  let saves = 0;
  const dependencies = {
    getOperatorActor,
    now: () => fixedTimestamp,
    saveWorkflowState(_institutionId, patch) {
      saves += 1;
      state = { ...state, salesNotes: { ...state.salesNotes, ...(patch.salesNotes ?? {}) } };
      return structuredClone(state);
    },
  };
  return { before, dependencies, getState: () => state, getSaves: () => saves };
}

async function run(body: unknown, token?: string) {
  const subject = fixture();
  const previousToken = process.env.NOVANUSA_OPERATOR_TOKEN;
  process.env.NOVANUSA_OPERATOR_TOKEN = validToken;
  try {
    const response = await executeSalesNotesCommand(commandRequest(body, token), "inst-1", subject.dependencies);
    return { ...subject, response, payload: await response.json() };
  } finally {
    if (previousToken === undefined) delete process.env.NOVANUSA_OPERATOR_TOKEN;
    else process.env.NOVANUSA_OPERATOR_TOKEN = previousToken;
  }
}

test("Sales Notes command fails closed for missing and invalid authentication", async () => {
  for (const token of [undefined, "invalid-token"]) {
    const result = await run({ operation: "update", notes: validNotes }, token);
    assert.equal(result.response.status, 401);
    assert.deepEqual(result.payload, { ok: false, error: { code: "UNAUTHORIZED", message: "Unauthorized." } });
    assert.equal(result.getSaves(), 0);
  }
});

test("valid operator can update Sales Notes with server authority", async () => {
  const result = await run({ operation: "update", notes: validNotes }, validToken);
  assert.equal(result.response.status, 200);
  assert.equal(result.payload.ok, true);
  assert.deepEqual(result.payload.salesNotes, {
    ...validNotes,
    savedAt: fixedTimestamp,
    updatedAt: fixedTimestamp,
    updatedBy: "local-operator",
  });
  assert.equal(result.getSaves(), 1);
});

test("unknown, cross-slice, client-authority, and malformed operations are rejected", async () => {
  const cases = [
    [{ operation: "update", notes: { ...validNotes, unknown: "value" } }, "INVALID_NOTES_FIELDS"],
    [{ operation: "update", notes: validNotes, draft: {} }, "UNKNOWN_FIELD"],
    [{ operation: "update", notes: validNotes, updatedAt: "client-time" }, "UNKNOWN_FIELD"],
    [{ operation: "update", notes: validNotes, updatedBy: "client-actor" }, "UNKNOWN_FIELD"],
    [{ operation: "erase" }, "INVALID_OPERATION"],
    [{ notes: validNotes }, "INVALID_OPERATION"],
  ] as const;
  for (const [body, code] of cases) {
    const result = await run(body, validToken);
    assert.equal(result.response.status, 400);
    assert.equal(result.payload.error.code, code);
    assert.equal(result.getSaves(), 0);
  }
});

test("malformed JSON is rejected without persistence", async () => {
  const subject = fixture();
  const previousToken = process.env.NOVANUSA_OPERATOR_TOKEN;
  process.env.NOVANUSA_OPERATOR_TOKEN = validToken;
  try {
    const request = new Request("http://localhost/api/institutions/inst-1/sales-notes", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-novanusa-operator-token": validToken },
      body: "{not-json",
    });
    const response = await executeSalesNotesCommand(request, "inst-1", subject.dependencies);
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { ok: false, error: { code: "MALFORMED_JSON", message: "Request body must be valid JSON." } });
    assert.equal(subject.getSaves(), 0);
  } finally {
    if (previousToken === undefined) delete process.env.NOVANUSA_OPERATOR_TOKEN;
    else process.env.NOVANUSA_OPERATOR_TOKEN = previousToken;
  }
});

test("over-limit note is rejected without persistence", async () => {
  const result = await run({ operation: "update", notes: { ...validNotes, internalNotes: "x".repeat(SALES_NOTES_MAX_FIELD_LENGTH + 1) } }, validToken);
  assert.equal(result.response.status, 400);
  assert.equal(result.payload.error.code, "NOTE_TOO_LONG");
  assert.equal(result.getSaves(), 0);
});

test("update changes only the Sales Notes slice", async () => {
  const result = await run({ operation: "update", notes: validNotes }, validToken);
  const after = result.getState();
  assert.notDeepEqual(after.salesNotes, result.before.salesNotes);
  assert.deepEqual(after.draft, result.before.draft);
  assert.deepEqual(after.nextAction, result.before.nextAction);
  assert.deepEqual(after.timeline, result.before.timeline);
  assert.deepEqual(after.emailSend, result.before.emailSend);
});

test("explicit clear changes only Sales Notes and uses server metadata", async () => {
  const result = await run({ operation: "clear" }, validToken);
  assert.equal(result.response.status, 200);
  assert.deepEqual(result.payload.salesNotes, {
    contactPerson: "",
    conversationNotes: "",
    customerInterest: "",
    requestedDocuments: "",
    internalNotes: "",
    savedAt: fixedTimestamp,
    updatedAt: fixedTimestamp,
    updatedBy: "local-operator",
  });
  const after = result.getState();
  assert.deepEqual(after.draft, result.before.draft);
  assert.deepEqual(after.nextAction, result.before.nextAction);
  assert.deepEqual(after.timeline, result.before.timeline);
  assert.deepEqual(after.emailSend, result.before.emailSend);
});

test("clear rejects extra values instead of inferring semantics", async () => {
  const result = await run({ operation: "clear", notes: validNotes }, validToken);
  assert.equal(result.response.status, 400);
  assert.equal(result.payload.error.code, "UNKNOWN_FIELD");
  assert.equal(result.getSaves(), 0);
});

test("legacy Sales Notes normalize with backward-compatible metadata defaults", () => {
  const legacy = { ...validNotes, savedAt: "legacy-time" };
  const normalized = { ...createDefaultWorkflowState().salesNotes, ...legacy };
  assert.equal(normalized.savedAt, "legacy-time");
  assert.equal(normalized.updatedAt, null);
  assert.equal(normalized.updatedBy, null);
  const storeSource = fs.readFileSync(path.join(process.cwd(), "src", "lib", "workflow-state-store.ts"), "utf8");
  assert.match(storeSource, /salesNotes: \{ \.\.\.defaults\.salesNotes, \.\.\.\(value\?\.salesNotes \?\? \{\}\) \}/);
});

test("aggregate GET and draft-only POST contracts remain unchanged", () => {
  const routeSource = fs.readFileSync(path.join(process.cwd(), "src", "app", "api", "institutions", "[id]", "workflow-state", "route.ts"), "utf8");
  assert.match(routeSource, /NextResponse\.json\(getWorkflowState\(id\)\)/);
  assert.match(routeSource, /patch\.emailSend \|\| patch\.timeline \|\| patch\.salesNotes \|\| patch\.nextAction/);
  assert.match(routeSource, /Only draft workflow transitions are accepted/);
});

test("Sales Notes UI uses authenticated explicit commands and server response hydration", async () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "app", "institutions", "[id]", "SalesNotes.tsx"), "utf8");
  assert.match(source, /sendSalesNotesCommandIfActive/);
  assert.match(source, /operation: "update", notes/);
  assert.match(source, /operation: "clear"/);
  assert.doesNotMatch(source, /postWorkflowState|new Date\(\)\.toISOString/);

  const clientSource = fs.readFileSync(path.join(process.cwd(), "src", "lib", "sales-notes-client.ts"), "utf8");
  assert.match(clientSource, /\/sales-notes/);
  assert.match(clientSource, /operatorHeaders\(operatorToken\)/);
  assert.match(clientSource, /if \(!operatorReady \|\| !operatorToken\) return null/);
  assert.match(source, /setNotes\(\{/);
  assert.match(source, /setTersimpanAt\(salesNotes\.updatedAt\)/);
});
