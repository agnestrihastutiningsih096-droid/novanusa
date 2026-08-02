/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { getOperatorActor } from "./email-sender.ts";
import { executeNextActionCommand, NEXT_ACTION_MAX_NOTE_LENGTH } from "./next-action-command.ts";
import { createDefaultWorkflowState } from "./workflow-state-types.ts";

const validToken = "valid-next-action-token";
const fixedTimestamp = "2026-08-01T12:00:00.000Z";
const validNextAction = { action: "Schedule Meeting", note: "Hubungi kepala pengadaan." };

function commandRequest(body: unknown, token?: string) {
  return new Request("http://localhost/api/institutions/inst-1/next-action", {
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
    salesNotes: { ...state.salesNotes, internalNotes: "Existing sales note" },
    nextAction: { ...state.nextAction, action: "Call Again", note: "Existing action", savedAt: "old-action-time" },
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
      state = { ...state, nextAction: { ...state.nextAction, ...(patch.nextAction ?? {}) } };
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
    const response = await executeNextActionCommand(commandRequest(body, token), "inst-1", subject.dependencies);
    return { ...subject, response, payload: await response.json() };
  } finally {
    if (previousToken === undefined) delete process.env.NOVANUSA_OPERATOR_TOKEN;
    else process.env.NOVANUSA_OPERATOR_TOKEN = previousToken;
  }
}

test("Next Action command fails closed for missing and invalid authentication", async () => {
  for (const token of [undefined, "invalid-token"]) {
    const result = await run({ operation: "update", nextAction: validNextAction }, token);
    assert.equal(result.response.status, 401);
    assert.deepEqual(result.payload, { ok: false, error: { code: "UNAUTHORIZED", message: "Unauthorized." } });
    assert.equal(result.getSaves(), 0);
  }
});

test("valid operator can update Next Action with server authority", async () => {
  const result = await run({ operation: "update", nextAction: validNextAction }, validToken);
  assert.equal(result.response.status, 200);
  assert.deepEqual(result.payload, {
    ok: true,
    nextAction: { ...validNextAction, savedAt: fixedTimestamp, updatedAt: fixedTimestamp, updatedBy: "local-operator" },
  });
  assert.equal(result.getSaves(), 1);
});

test("unknown, cross-slice, client-authority, invalid action, and malformed operations are rejected", async () => {
  const cases = [
    [{ operation: "update", nextAction: { ...validNextAction, unknown: "value" } }, "INVALID_NEXT_ACTION_FIELDS"],
    [{ operation: "update", nextAction: validNextAction, draft: {} }, "UNKNOWN_FIELD"],
    [{ operation: "update", nextAction: validNextAction, salesNotes: {} }, "UNKNOWN_FIELD"],
    [{ operation: "update", nextAction: { ...validNextAction, savedAt: "client-time" } }, "INVALID_NEXT_ACTION_FIELDS"],
    [{ operation: "update", nextAction: { ...validNextAction, updatedAt: "client-time" } }, "INVALID_NEXT_ACTION_FIELDS"],
    [{ operation: "update", nextAction: { ...validNextAction, updatedBy: "client-actor" } }, "INVALID_NEXT_ACTION_FIELDS"],
    [{ operation: "update", nextAction: { action: "Create Opportunity", note: "No" } }, "INVALID_ACTION"],
    [{ operation: "erase" }, "INVALID_OPERATION"],
    [{ nextAction: validNextAction }, "INVALID_OPERATION"],
  ] as const;
  for (const [body, code] of cases) {
    const result = await run(body, validToken);
    assert.equal(result.response.status, 400);
    assert.equal(result.payload.error.code, code);
    assert.equal(result.getSaves(), 0);
  }
});

test("over-limit note and implicit clear payloads are rejected", async () => {
  const tooLong = await run({ operation: "update", nextAction: { action: "Other", note: "x".repeat(NEXT_ACTION_MAX_NOTE_LENGTH + 1) } }, validToken);
  assert.equal(tooLong.payload.error.code, "NOTE_TOO_LONG");
  for (const nextAction of [null, {}, { action: "Call Again" }]) {
    const result = await run({ operation: "update", nextAction }, validToken);
    assert.equal(result.response.status, 400);
    assert.equal(result.getSaves(), 0);
  }
});

test("malformed JSON is rejected without persistence", async () => {
  const subject = fixture();
  const previousToken = process.env.NOVANUSA_OPERATOR_TOKEN;
  process.env.NOVANUSA_OPERATOR_TOKEN = validToken;
  try {
    const response = await executeNextActionCommand(new Request("http://localhost/api/institutions/inst-1/next-action", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-novanusa-operator-token": validToken },
      body: "{not-json",
    }), "inst-1", subject.dependencies);
    assert.equal(response.status, 400);
    assert.equal((await response.json()).error.code, "MALFORMED_JSON");
    assert.equal(subject.getSaves(), 0);
  } finally {
    if (previousToken === undefined) delete process.env.NOVANUSA_OPERATOR_TOKEN;
    else process.env.NOVANUSA_OPERATOR_TOKEN = previousToken;
  }
});

for (const operation of ["update", "clear"] as const) {
  test(`${operation} changes only the Next Action slice`, async () => {
    const body = operation === "update" ? { operation, nextAction: validNextAction } : { operation };
    const result = await run(body, validToken);
    const after = result.getState();
    assert.notDeepEqual(after.nextAction, result.before.nextAction);
    for (const sibling of ["draft", "salesNotes", "timeline", "emailSend"] as const) {
      assert.deepEqual(after[sibling], result.before[sibling]);
    }
    assert.equal(after.nextAction.updatedAt, fixedTimestamp);
    assert.equal(after.nextAction.updatedBy, "local-operator");
  });
}

test("clear is explicit, rejects fields, and records server-owned clear metadata", async () => {
  const result = await run({ operation: "clear" }, validToken);
  assert.deepEqual(result.payload.nextAction, {
    action: "Call Again", note: "", savedAt: null, updatedAt: fixedTimestamp, updatedBy: "local-operator",
  });
  const invalid = await run({ operation: "clear", nextAction: validNextAction }, validToken);
  assert.equal(invalid.payload.error.code, "UNKNOWN_FIELD");
  assert.equal(invalid.getSaves(), 0);
});

test("legacy Next Action records normalize with backward-compatible metadata defaults", () => {
  const legacy = { action: "Send Catalog", note: "Legacy", savedAt: "legacy-time" };
  const normalized = { ...createDefaultWorkflowState().nextAction, ...legacy };
  assert.equal(normalized.updatedAt, null);
  assert.equal(normalized.updatedBy, null);
  const storeSource = fs.readFileSync(path.join(process.cwd(), "src", "lib", "workflow-state-store.ts"), "utf8");
  assert.match(storeSource, /nextAction: \{ \.\.\.defaults\.nextAction, \.\.\.\(value\?\.nextAction \?\? \{\}\) \}/);
});

test("aggregate GET remains complete and workflow-state POST remains draft-only", () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "app", "api", "institutions", "[id]", "workflow-state", "route.ts"), "utf8");
  assert.match(source, /NextResponse\.json\(getWorkflowState\(id\)\)/);
  assert.match(source, /patch\.emailSend \|\| patch\.timeline \|\| patch\.salesNotes \|\| patch\.nextAction/);
  assert.match(source, /Only draft workflow transitions are accepted/);
});

test("Next Action client blocks inactive writes and sends authenticated feature commands", () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "lib", "next-action-client.ts"), "utf8");
  assert.match(source, /if \(!operatorReady \|\| !operatorToken\) return null/);
  assert.match(source, /\/next-action/);
  assert.match(source, /operatorHeaders\(operatorToken\)/);
  assert.match(source, /body: JSON\.stringify\(command\)/);
});

test("Next Action UI uses aggregate hydration and explicit server-response commands", () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "app", "institutions", "[id]", "NextAction.tsx"), "utf8");
  assert.match(source, /fetchWorkflowStateIfActive/);
  assert.match(source, /sendNextActionCommandIfActive/);
  assert.match(source, /operation: "update", nextAction: \{ action, note \}/);
  assert.match(source, /operation: "clear"/);
  assert.match(source, /setSavedAt\(nextAction\.savedAt\)/);
  assert.doesNotMatch(source, /postWorkflowState|new Date\(\)\.toISOString/);
});
