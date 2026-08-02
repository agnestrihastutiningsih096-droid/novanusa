/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { getOperatorActor } from "./email-sender.ts";
import { fetchWorkflowStateIfActive } from "./operator-auth.ts";

const workspace = process.cwd();

test("protected workflow GET is not fired before explicit activation", () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return new Response();
  };

  assert.equal(fetchWorkflowStateIfActive("inst-1", "", false, undefined, fetchImpl), null);
  assert.equal(fetchWorkflowStateIfActive("inst-1", "typed-but-inactive", false, undefined, fetchImpl), null);
  assert.equal(calls, 0);
});

test("all four protected component request paths use the shared authenticated helper", async () => {
  const components = ["DraftGenerator", "SalesNotes", "NextAction", "CommunicationTimeline"];
  for (const component of components) {
    const source = fs.readFileSync(path.join(workspace, "src", "app", "institutions", "[id]", `${component}.tsx`), "utf8");
    assert.match(source, /fetchWorkflowStateIfActive/);
    assert.doesNotMatch(source, /fetch\(`\/api\/institutions\/\$\{encodeURIComponent\([^)]*\)\}\/workflow-state/);
  }

  const seenHeaders: string[] = [];
  const fetchImpl = async (_input: RequestInfo | URL, init?: RequestInit) => {
    seenHeaders.push(new Headers(init?.headers).get("x-novanusa-operator-token") ?? "");
    return new Response("{}", { status: 200 });
  };
  await Promise.all(components.map(() => fetchWorkflowStateIfActive("inst-1", "shared-memory-token", true, undefined, fetchImpl)));
  assert.deepEqual(seenHeaders, components.map(() => "shared-memory-token"));
});

test("invalid active token remains unauthorized", async () => {
  const previousToken = process.env.NOVANUSA_OPERATOR_TOKEN;
  process.env.NOVANUSA_OPERATOR_TOKEN = "valid-token-123456789";
  try {
    const response = await fetchWorkflowStateIfActive("inst-1", "invalid-token", true, undefined, async (input, init) => {
      const request = new Request(new URL(String(input), "http://localhost"), init);
      return new Response(null, { status: getOperatorActor(request) ? 200 : 401 });
    });
    assert.equal(response?.status, 401);
  } finally {
    if (previousToken === undefined) delete process.env.NOVANUSA_OPERATOR_TOKEN;
    else process.env.NOVANUSA_OPERATOR_TOKEN = previousToken;
  }
});

test("deactivation suppresses subsequent protected requests", async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return new Response("{}", { status: 200 });
  };

  await fetchWorkflowStateIfActive("inst-1", "memory-token", true, undefined, fetchImpl);
  assert.equal(calls, 1);
  assert.equal(fetchWorkflowStateIfActive("inst-1", "", false, undefined, fetchImpl), null);
  assert.equal(calls, 1);
});

test("operator token state is memory-only and does not alter workflow contracts", () => {
  const contextSource = fs.readFileSync(path.join(workspace, "src", "app", "institutions", "[id]", "InstitutionOperatorContext.tsx"), "utf8");
  const routeSource = fs.readFileSync(path.join(workspace, "src", "app", "api", "institutions", "[id]", "workflow-state", "route.ts"), "utf8");

  assert.match(contextSource, /useState\(""\)/);
  assert.doesNotMatch(contextSource, /localStorage|sessionStorage|document\.cookie|process\.env|fetch\(/);
  assert.match(contextSource, /setOperatorToken\(""\)/);
  assert.match(routeSource, /patch\.emailSend \|\| patch\.timeline \|\| patch\.salesNotes \|\| patch\.nextAction/);
  assert.match(routeSource, /Only draft workflow transitions are accepted/);
});
