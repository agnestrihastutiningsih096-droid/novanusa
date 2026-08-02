/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { getOperatorActor } from "./email-sender.ts";
import { executeTimelineCommand } from "./timeline-command.ts";
import { createDefaultWorkflowState } from "./workflow-state-types.ts";

const validToken = "valid-timeline-token";
const fixedTimestamp = "2026-08-01T12:00:00.000Z";

function commandRequest(body: unknown, token?: string) {
  return new Request("http://localhost/api/institutions/inst-1/timeline", {
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
    nextAction: { ...state.nextAction, action: "Schedule Meeting", note: "Existing action" },
    timeline: {
      completedEvents: ["COLD_EMAIL_DRAFTED", "PHONE_CALL"],
      eventTimestamps: { COLD_EMAIL_DRAFTED: "derived-legacy-time", PHONE_CALL: "old-phone-time" },
      currentStage: "Telepon",
      updatedAt: "old-timeline-time",
      updatedBy: "previous-operator",
    },
    emailSend: { ...state.emailSend, intendedRecipient: "institution@example.go.id" },
  };
  const before = structuredClone(state);
  const outreachStatus = "SENT";
  let saves = 0;
  const dependencies = {
    getOperatorActor,
    now: () => fixedTimestamp,
    getWorkflowState: () => structuredClone(state),
    saveWorkflowState(_institutionId, patch) {
      saves += 1;
      state = { ...state, timeline: { ...state.timeline, ...(patch.timeline ?? {}) } };
      return structuredClone(state);
    },
  };
  return { before, outreachStatus, dependencies, getState: () => state, getSaves: () => saves };
}

async function run(body: unknown, token?: string) {
  const subject = fixture();
  const previousToken = process.env.NOVANUSA_OPERATOR_TOKEN;
  process.env.NOVANUSA_OPERATOR_TOKEN = validToken;
  try {
    const response = await executeTimelineCommand(commandRequest(body, token), "inst-1", subject.dependencies);
    return { ...subject, response, payload: await response.json() };
  } finally {
    if (previousToken === undefined) delete process.env.NOVANUSA_OPERATOR_TOKEN;
    else process.env.NOVANUSA_OPERATOR_TOKEN = previousToken;
  }
}

test("Timeline command fails closed for missing and invalid authentication", async () => {
  for (const token of [undefined, "invalid-token"]) {
    const result = await run({ operation: "complete", event: "MEETING" }, token);
    assert.equal(result.response.status, 401);
    assert.deepEqual(result.payload, { ok: false, error: { code: "UNAUTHORIZED", message: "Unauthorized." } });
    assert.equal(result.getSaves(), 0);
  }
});

test("valid operator completes a manual event with server authority", async () => {
  const result = await run({ operation: "complete", event: "MEETING" }, validToken);
  assert.equal(result.response.status, 200);
  assert.equal(result.payload.ok, true);
  assert.deepEqual(result.payload.timeline.completedEvents, ["COLD_EMAIL_DRAFTED", "PHONE_CALL", "MEETING"]);
  assert.equal(result.payload.timeline.eventTimestamps.MEETING, fixedTimestamp);
  assert.equal(result.payload.timeline.updatedAt, fixedTimestamp);
  assert.equal(result.payload.timeline.updatedBy, "local-operator");
  assert.equal(result.getSaves(), 1);
});

test("malformed operation, unknown fields, authority fields, and cross-slice payloads are rejected", async () => {
  const cases = [
    [{ operation: "remove", event: "PHONE_CALL" }, "INVALID_OPERATION"],
    [{ event: "PHONE_CALL" }, "INVALID_OPERATION"],
    [{ operation: "complete", event: "PHONE_CALL", unknown: true }, "UNKNOWN_FIELD"],
    [{ operation: "complete", event: "PHONE_CALL", completedAt: "client-time" }, "UNKNOWN_FIELD"],
    [{ operation: "complete", event: "PHONE_CALL", updatedAt: "client-time" }, "UNKNOWN_FIELD"],
    [{ operation: "complete", event: "PHONE_CALL", updatedBy: "client-actor" }, "UNKNOWN_FIELD"],
    [{ operation: "complete", event: "PHONE_CALL", draft: {} }, "UNKNOWN_FIELD"],
    [{ operation: "reset", event: "PHONE_CALL", timeline: {} }, "UNKNOWN_FIELD"],
  ] as const;
  for (const [body, code] of cases) {
    const result = await run(body, validToken);
    assert.equal(result.response.status, 400);
    assert.equal(result.payload.error.code, code);
    assert.equal(result.getSaves(), 0);
  }
});

test("unknown and derived event identifiers fail closed", async () => {
  const unknown = await run({ operation: "complete", event: "CUSTOM_EVENT" }, validToken);
  assert.equal(unknown.payload.error.code, "UNKNOWN_EVENT");
  for (const event of ["COLD_EMAIL_DRAFTED", "DRAFT_APPROVED", "EMAIL_SENT", "CLOSED_WON", "CLOSED_LOST"]) {
    const derived = await run({ operation: "complete", event }, validToken);
    assert.equal(derived.response.status, 400);
    assert.equal(derived.payload.error.code, "DERIVED_EVENT_READ_ONLY");
    assert.equal(derived.getSaves(), 0);
  }
});

test("malformed JSON is rejected without persistence", async () => {
  const subject = fixture();
  const previousToken = process.env.NOVANUSA_OPERATOR_TOKEN;
  process.env.NOVANUSA_OPERATOR_TOKEN = validToken;
  try {
    const response = await executeTimelineCommand(new Request("http://localhost/api/institutions/inst-1/timeline", {
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

for (const [operation, event] of [["complete", "MEETING"], ["reset", "PHONE_CALL"]] as const) {
  test(`${operation} changes only timeline and never outreach_status`, async () => {
    const result = await run({ operation, event }, validToken);
    const after = result.getState();
    assert.notDeepEqual(after.timeline, result.before.timeline);
    for (const sibling of ["draft", "salesNotes", "nextAction", "emailSend"] as const) {
      assert.deepEqual(after[sibling], result.before[sibling]);
    }
    assert.equal(result.outreachStatus, "SENT");
    assert.equal(after.timeline.completedEvents.includes("COLD_EMAIL_DRAFTED"), true);
    assert.equal(after.timeline.eventTimestamps.COLD_EMAIL_DRAFTED, "derived-legacy-time");
  });
}

test("reset removes only the targeted manual event and records server metadata", async () => {
  const result = await run({ operation: "reset", event: "PHONE_CALL" }, validToken);
  assert.deepEqual(result.payload.timeline.completedEvents, ["COLD_EMAIL_DRAFTED"]);
  assert.equal(result.payload.timeline.eventTimestamps.PHONE_CALL, undefined);
  assert.equal(result.payload.timeline.updatedAt, fixedTimestamp);
  assert.equal(result.payload.timeline.updatedBy, "local-operator");
});

test("repeated complete and reset are no-op successes with canonical unchanged metadata", async () => {
  const complete = await run({ operation: "complete", event: "PHONE_CALL" }, validToken);
  assert.equal(complete.response.status, 200);
  assert.equal(complete.getSaves(), 0);
  assert.deepEqual(complete.payload.timeline, complete.before.timeline);

  const reset = await run({ operation: "reset", event: "MEETING" }, validToken);
  assert.equal(reset.response.status, 200);
  assert.equal(reset.getSaves(), 0);
  assert.deepEqual(reset.payload.timeline, reset.before.timeline);
});

test("legacy timeline records normalize with backward-compatible actor metadata", () => {
  const legacy = { completedEvents: ["PHONE_CALL"], eventTimestamps: { PHONE_CALL: "legacy-time" }, currentStage: "Telepon", updatedAt: "legacy-time" };
  const normalized = { ...createDefaultWorkflowState().timeline, ...legacy };
  assert.equal(normalized.updatedBy, null);
  const storeSource = fs.readFileSync(path.join(process.cwd(), "src", "lib", "workflow-state-store.ts"), "utf8");
  assert.match(storeSource, /timeline: \{ \.\.\.defaults\.timeline, \.\.\.\(value\?\.timeline \?\? \{\}\) \}/);
});

test("aggregate contracts and passing sibling commands remain isolated", () => {
  const routeSource = fs.readFileSync(path.join(process.cwd(), "src", "app", "api", "institutions", "[id]", "workflow-state", "route.ts"), "utf8");
  assert.match(routeSource, /NextResponse\.json\(getWorkflowState\(id\)\)/);
  assert.match(routeSource, /patch\.emailSend \|\| patch\.timeline \|\| patch\.salesNotes \|\| patch\.nextAction/);
  assert.match(routeSource, /Only draft workflow transitions are accepted/);
  for (const command of ["sales-notes-command.ts", "next-action-command.ts"]) {
    const source = fs.readFileSync(path.join(process.cwd(), "src", "lib", command), "utf8");
    assert.doesNotMatch(source, /timeline:/);
  }
});

test("Timeline client and UI use authenticated explicit commands and server hydration", () => {
  const client = fs.readFileSync(path.join(process.cwd(), "src", "lib", "timeline-client.ts"), "utf8");
  assert.match(client, /if \(!operatorReady \|\| !operatorToken\) return null/);
  assert.match(client, /\/timeline/);
  assert.match(client, /operatorHeaders\(operatorToken\)/);

  const ui = fs.readFileSync(path.join(process.cwd(), "src", "app", "institutions", "[id]", "CommunicationTimeline.tsx"), "utf8");
  assert.match(ui, /fetchWorkflowStateIfActive/);
  assert.match(ui, /operation: "complete", event/);
  assert.match(ui, /operation: "reset", event/);
  assert.match(ui, /setEvents\(mergeTimeline\(timeline, emailSend, initialCompleted\)\)/);
  assert.match(ui, /const manualEvent = isManualTimelineEventKey\(event\.key\)/);
  assert.match(ui, /state\.derived \? "Proyeksi outreach" : "Overlay manual"/);
  assert.doesNotMatch(ui, /postWorkflowState|new Date\(\)\.toISOString|outreachStatus\s*=/);
});
