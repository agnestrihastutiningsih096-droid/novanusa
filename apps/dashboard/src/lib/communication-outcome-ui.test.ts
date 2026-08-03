/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fetchLatestGenericCommunicationOutcomeIfActive, sendGenericCommunicationOutcomeIfActive } from "./communication-outcome-client.ts";

const componentSource = fs.readFileSync(path.join(process.cwd(), "src", "app", "institutions", "[id]", "CommunicationOutcome.tsx"), "utf8");

test("Communication Outcome form renders the closed registry and optional note", () => {
  assert.match(componentSource, /COMMUNICATION_OUTCOMES\.map/);
  assert.match(componentSource, /aria-label="Hasil komunikasi"/);
  assert.match(componentSource, /Catatan operator opsional/);
  assert.match(componentSource, /maxLength=\{2000\}/);
});

test("valid submission generates commandId, authenticates, and remains generic", async () => {
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;
  const response = await sendGenericCommunicationOutcomeIfActive(
    "inst/1", "operator-secret", true, "interested", "  Catatan  ",
    async (url, init) => {
      capturedUrl = String(url);
      capturedInit = init;
      return new Response(JSON.stringify({ data: {}, audit: {} }), { status: 201 });
    },
    () => "11111111-1111-4111-8111-111111111111",
  );
  assert.equal(response?.status, 201);
  assert.equal(capturedUrl, "/api/institutions/inst%2F1/communication-outcomes");
  assert.equal(new Headers(capturedInit?.headers).get("x-novanusa-operator-token"), "operator-secret");
  assert.deepEqual(JSON.parse(String(capturedInit?.body)), {
    commandId: "11111111-1111-4111-8111-111111111111",
    outcome: "interested",
    note: "Catatan",
  });
  assert.doesNotMatch(String(capturedInit?.body), /procurementIdentityId/);
});

test("a new client commandId is generated per submission", async () => {
  let generated = 0;
  const bodies: string[] = [];
  const send = () => sendGenericCommunicationOutcomeIfActive("inst-1", "token", true, "no_response", "", async (_url, init) => {
    bodies.push(String(init?.body));
    return new Response("{}", { status: 201 });
  }, () => `00000000-0000-4000-8000-${String(++generated).padStart(12, "0")}`);
  await send();
  await send();
  assert.notEqual(JSON.parse(bodies[0]).commandId, JSON.parse(bodies[1]).commandId);
  assert.deepEqual(Object.keys(JSON.parse(bodies[0])).sort(), ["commandId", "outcome"]);
});

test("inactive operator state sends no request and UI displays unauthorized state", () => {
  let calls = 0;
  const result = sendGenericCommunicationOutcomeIfActive("inst-1", "", false, "interested", "", async () => {
    calls += 1;
    return new Response();
  });
  assert.equal(result, null);
  assert.equal(calls, 0);
  assert.match(componentSource, /disabled=\{!operatorReady \|\| !operatorToken \|\| submitting \|\| hydrating\}/);
  assert.match(componentSource, /Token operator diperlukan/);
});

test("UI hydration fetches the generic endpoint with the operator token", async () => {
  let capturedInit: RequestInit | undefined;
  const response = await fetchLatestGenericCommunicationOutcomeIfActive("inst-1", "operator-secret", true, async (_url, init) => {
    capturedInit = init;
    return new Response(JSON.stringify({ data: null }));
  });
  assert.equal(response?.status, 200);
  assert.equal(new Headers(capturedInit?.headers).get("x-novanusa-operator-token"), "operator-secret");
  assert.equal(capturedInit?.method, undefined);
  assert.match(componentSource, /useEffect\(\(\) =>/);
  assert.match(componentSource, /fetchLatestGenericCommunicationOutcomeIfActive/);
  assert.match(componentSource, /setLatest\(payload\.data \?\? null\)/);
});

test("UI hydration exposes loading, empty, success, and deterministic error states", () => {
  assert.match(componentSource, /Memuat communication outcome terbaru/);
  assert.match(componentSource, /Belum ada communication outcome/);
  assert.match(componentSource, /Communication outcome terbaru dimuat/);
  assert.match(componentSource, /error\?\.code/);
  assert.match(componentSource, /error\?\.message/);
});

test("successful POST is followed by GET and only the authoritative GET payload updates latest", async () => {
  const postRecord = { id: "post-result", outcome: "interested" };
  const persistedRecord = { id: "persisted-result", outcome: "no_decision" };
  const calls: string[] = [];
  const fetchImpl = async (_url: RequestInfo | URL, init?: RequestInit) => {
    calls.push(init?.method ?? "GET");
    return init?.method === "POST"
      ? new Response(JSON.stringify({ data: postRecord, audit: { eventId: "audit-1" } }), { status: 201 })
      : new Response(JSON.stringify({ data: persistedRecord }), { status: 200 });
  };
  const postResponse = await sendGenericCommunicationOutcomeIfActive("inst-1", "token", true, "interested", "", fetchImpl);
  assert.equal(postResponse?.ok, true);
  const getResponse = await fetchLatestGenericCommunicationOutcomeIfActive("inst-1", "token", true, fetchImpl);
  assert.deepEqual((await getResponse!.json()).data, persistedRecord);
  assert.notDeepEqual(persistedRecord, postRecord);
  assert.deepEqual(calls, ["POST", "GET"]);

  assert.match(componentSource, /sendGenericCommunicationOutcomeIfActive[\s\S]*fetchLatestGenericCommunicationOutcomeIfActive/);
  assert.match(componentSource, /setLatest\(latestPayload\.data \?\? null\)/);
  assert.doesNotMatch(componentSource, /setLatest\(commandPayload\.data/);
});

test("success and deterministic command errors remain displayed", () => {
  assert.match(componentSource, /Communication outcome terbaru/);
  assert.match(componentSource, /latest\.actor/);
  assert.match(componentSource, /latest\.recordedAt/);
  assert.match(componentSource, /error\?\.code/);
  assert.match(componentSource, /error\?\.message/);
  assert.doesNotMatch(componentSource, /procurementIdentityId|fetchWorkflowState|saveWorkflowState/);
});
