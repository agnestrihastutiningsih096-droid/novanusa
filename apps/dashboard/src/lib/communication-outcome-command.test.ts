import assert from "node:assert/strict";
import test from "node:test";
import type { CommunicationOutcomeAppend, CommunicationOutcomeAppendResult, CommunicationOutcomeRecord } from "./communication-outcome.ts";
import { executeCommunicationOutcomeCommand, executeCommunicationOutcomeRead } from "./communication-outcome-command.ts";
import { findLatestGenericCommunicationOutcome } from "./communication-outcome-store.ts";

const commandOne = "11111111-1111-4111-8111-111111111111";

function request(body: unknown, authenticated = true) {
  return new Request("http://localhost/api/institutions/inst-1/communication-outcomes", {
    method: "POST",
    headers: authenticated ? { "x-test-operator": "yes", "content-type": "application/json" } : { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function harness() {
  const appends: CommunicationOutcomeAppend[] = [];
  const commands = new Map<string, CommunicationOutcomeAppend>();
  let id = 0;
  const append = (value: CommunicationOutcomeAppend): CommunicationOutcomeAppendResult => {
    const prior = commands.get(value.commandId);
    if (prior) {
      if (prior.canonicalContent !== value.canonicalContent) return { status: "conflict" };
      return { status: "replayed", result: { data: prior.record, audit: { eventId: prior.audit.eventId } } };
    }
    commands.set(value.commandId, value);
    appends.push(value);
    return { status: "created", result: { data: value.record, audit: { eventId: value.audit.eventId } } };
  };
  return {
    appends,
    dependencies: {
      getOperatorActor: (incoming: Request) => incoming.headers.get("x-test-operator") === "yes" ? "operator-1" : null,
      institutionExists: (institutionId: string) => institutionId === "inst-1" || institutionId === "inst-2",
      procurementIdentityBelongsToInstitution: () => false,
      getCommand: (commandId: string) => {
        const prior = commands.get(commandId);
        return prior ? { canonicalContent: prior.canonicalContent, result: { data: prior.record, audit: { eventId: prior.audit.eventId } } } : null;
      },
      append,
      now: () => "2026-08-03T00:00:00.000Z",
      createId: () => `server-${++id}`,
    },
  };
}

test("records a valid generic outcome with server-owned metadata", async () => {
  const state = harness();
  const response = await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "interested", note: "  Useful call  " }), "inst-1", state.dependencies);
  assert.equal(response.status, 201);
  assert.deepEqual(await response.json(), {
    data: { id: "server-1", institutionId: "inst-1", procurementIdentityId: null, outcome: "interested", note: "Useful call", actor: "operator-1", recordedAt: "2026-08-03T00:00:00.000Z" },
    audit: { eventId: "server-2" },
  });
});

test("rejects a supplied procurement identity when no canonical runtime authority exists", async () => {
  const state = harness();
  const response = await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "no_decision", procurementIdentityId: "proc-1" }), "inst-1", state.dependencies);
  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { error: { code: "PROCUREMENT_IDENTITY_NOT_FOUND", message: "Communication outcome could not be recorded." } });
  assert.equal(state.appends.length, 0);
});

test("rejects unknown fields", async () => {
  const state = harness();
  const response = await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "interested", actor: "client" }), "inst-1", state.dependencies);
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: { code: "VALIDATION_FAILED", message: "Communication outcome could not be recorded.", details: { fields: ["actor"] } } });
  assert.equal(state.appends.length, 0);
});

test("rejects an outcome outside the closed registry", async () => {
  const state = harness();
  const response = await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "INTERESTED" }), "inst-1", state.dependencies);
  assert.equal(response.status, 400);
  assert.deepEqual((await response.json()).error.details.fields, ["outcome"]);
});

test("rejects supplied procurement identities for every institution", async () => {
  for (const [institutionId, procurementIdentityId] of [["inst-1", "missing"], ["inst-2", "proc-1"]] as const) {
    const state = harness();
    const response = await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "interested", procurementIdentityId }), institutionId, state.dependencies);
    assert.equal(response.status, 404);
    assert.equal((await response.json()).error.code, "PROCUREMENT_IDENTITY_NOT_FOUND");
    assert.equal(state.appends.length, 0);
  }
});

test("an identical retry returns the original result without another append", async () => {
  const state = harness();
  const body = { commandId: commandOne, outcome: "no_response", note: "Called" };
  const first = await executeCommunicationOutcomeCommand(request(body), "inst-1", state.dependencies);
  const firstResult = await first.json();
  const retry = await executeCommunicationOutcomeCommand(request(body), "inst-1", state.dependencies);
  assert.equal(first.status, 201);
  assert.equal(retry.status, 200);
  assert.deepEqual(await retry.json(), firstResult);
  assert.equal(state.appends.length, 1);
});

test("conflicting global commandId reuse returns COMMAND_ID_REUSED", async () => {
  const state = harness();
  await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "interested" }), "inst-1", state.dependencies);
  const response = await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "not_interested" }), "inst-2", state.dependencies);
  assert.equal(response.status, 409);
  assert.equal((await response.json()).error.code, "COMMAND_ID_REUSED");
  assert.equal(state.appends.length, 1);
});

test("rejected procurement input cannot affect generic thread history", async () => {
  const state = harness();
  await executeCommunicationOutcomeCommand(request({ commandId: commandOne, outcome: "interested" }), "inst-1", state.dependencies);
  const rejected = await executeCommunicationOutcomeCommand(request({ commandId: "22222222-2222-4222-8222-222222222222", outcome: "invalid_contact", procurementIdentityId: "proc-1" }), "inst-1", state.dependencies);
  assert.equal(rejected.status, 404);
  assert.equal(state.appends.length, 1);
  assert.equal(state.appends[0].record.procurementIdentityId, null);
  assert.equal(state.appends[0].record.outcome, "interested");
});

test("rejects an unauthorized request before validation or persistence", async () => {
  const state = harness();
  const response = await executeCommunicationOutcomeCommand(request({ actor: "client" }, false), "inst-1", state.dependencies);
  assert.equal(response.status, 401);
  assert.deepEqual(await response.json(), { error: { code: "UNAUTHORIZED", message: "Communication outcome could not be recorded." } });
  assert.equal(state.appends.length, 0);
});

const genericRecord: CommunicationOutcomeRecord = {
  id: "outcome-generic",
  institutionId: "inst-1",
  procurementIdentityId: null,
  outcome: "interested",
  note: null,
  actor: "operator-1",
  recordedAt: "2026-08-03T01:00:00.000Z",
};

function readRequest(authenticated = true) {
  return new Request("http://localhost/api/institutions/inst-1/communication-outcomes", {
    headers: authenticated ? { "x-test-operator": "yes" } : {},
  });
}

test("GET returns the latest authoritative generic outcome", async () => {
  const response = executeCommunicationOutcomeRead(readRequest(), "inst-1", {
    getOperatorActor: () => "operator-1",
    institutionExists: () => true,
    getLatestGeneric: () => genericRecord,
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { data: genericRecord });
});

test("GET returns null when the generic thread is empty", async () => {
  const response = executeCommunicationOutcomeRead(readRequest(), "inst-1", {
    getOperatorActor: () => "operator-1",
    institutionExists: () => true,
    getLatestGeneric: () => null,
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { data: null });
});

test("GET rejects an unauthorized request with the deterministic error contract", async () => {
  let reads = 0;
  const response = executeCommunicationOutcomeRead(readRequest(false), "inst-1", {
    getOperatorActor: () => null,
    institutionExists: () => true,
    getLatestGeneric: () => { reads += 1; return genericRecord; },
  });
  assert.equal(response.status, 401);
  assert.deepEqual(await response.json(), { error: { code: "UNAUTHORIZED", message: "Communication outcome could not be recorded." } });
  assert.equal(reads, 0);
});

test("procurement-specific records are never returned as generic", () => {
  const records: CommunicationOutcomeRecord[] = [
    genericRecord,
    { ...genericRecord, id: "outcome-procurement", procurementIdentityId: "proc-1", outcome: "not_interested", recordedAt: "2026-08-03T02:00:00.000Z" },
  ];
  assert.deepEqual(findLatestGenericCommunicationOutcome(records, "inst-1"), genericRecord);
  assert.equal(findLatestGenericCommunicationOutcome(records, "inst-2"), null);
});
