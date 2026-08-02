/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { applyDraftTransition, createDefaultWorkflowState } from "./workflow-state-types.ts";
import { getEmailSendMode, getOperatorActor, sendEmailSafely } from "./email-sender.ts";
import { validateVerifiedContact } from "./institution-data.ts";

const originalEnv = { ...process.env };
const historyDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "novanusa-email-test-"));
process.env.NOVANUSA_EMAIL_HISTORY_PATH = path.join(historyDirectory, "history.json");

test.afterEach(() => {
  process.env = { ...originalEnv, NOVANUSA_EMAIL_HISTORY_PATH: process.env.NOVANUSA_EMAIL_HISTORY_PATH };
});

test.after(() => {
  fs.rmSync(historyDirectory, { recursive: true, force: true });
});

function testPayload() {
  return { to: "institution@example.go.id", subject: "Subject", body: "Body", metadata: { institutionId: "inst-1" } };
}

function verifiedProspect(overrides = {}) {
  return {
    institution_id: "inst-1",
    contact_email: "institution@example.go.id",
    contact_source_url: "https://example.go.id/contact",
    contact_status: "CONTACT_FOUND",
    contactVerificationStatus: "VERIFIED",
    contactVerifiedAt: "2026-07-27T00:00:00.000Z",
    contactVerifiedBy: "operator",
    contactVerificationSource: "official-website",
    ...overrides,
  };
}

function enableTestMode() {
  process.env.EMAIL_SEND_MODE = "test";
  process.env.EMAIL_FROM = "NovaNusa <test@verified.example>";
  process.env.RESEND_API_KEY = "test-key";
  process.env.EMAIL_TEST_RECIPIENT = "operator@example.com";
  process.env.EMAIL_TEST_RECIPIENT_ALLOWLIST = "operator@example.com";
}

test("mock is the default and does not call the network", async () => {
  delete process.env.EMAIL_SEND_MODE;
  let calls = 0;
  const result = await sendEmailSafely(testPayload(), async () => { calls += 1; throw new Error("network"); });
  assert.equal(getEmailSendMode(), "mock");
  assert.equal(result.status, "sent");
  assert.equal(calls, 0);
});

test("test mode redirects to the allowlisted recipient and marks the subject", async () => {
  enableTestMode();
  let request;
  const result = await sendEmailSafely(testPayload(), async (_url, init) => {
    request = JSON.parse(init.body);
    return new Response(JSON.stringify({ id: "resend-1" }), { status: 200 });
  });
  assert.equal(result.actualRecipient, "operator@example.com");
  assert.match(result.subject, /^\[TEST REDIRECT\]/);
  assert.equal(request.to, "operator@example.com");
});

test("test recipient outside allowlist is rejected without network", async () => {
  enableTestMode();
  process.env.EMAIL_TEST_RECIPIENT_ALLOWLIST = "someone-else@example.com";
  let calls = 0;
  const result = await sendEmailSafely(testPayload(), async () => { calls += 1; throw new Error("network"); });
  assert.equal(result.errorCode, "TEST_RECIPIENT_NOT_ALLOWLISTED");
  assert.equal(calls, 0);
});

test("real mode is rejected without network", async () => {
  process.env.EMAIL_SEND_MODE = "real";
  let calls = 0;
  const result = await sendEmailSafely(testPayload(), async () => { calls += 1; throw new Error("network"); });
  assert.equal(result.errorCode, "REAL_MODE_DISABLED");
  assert.equal(calls, 0);
});

test("missing provider credentials fail safely", async () => {
  enableTestMode();
  delete process.env.RESEND_API_KEY;
  const result = await sendEmailSafely(testPayload(), async () => { throw new Error("network"); });
  assert.equal(result.errorCode, "PROVIDER_CREDENTIALS_MISSING");
});

test("unauthorized approval and send requests have no server actor", () => {
  process.env.NOVANUSA_OPERATOR_TOKEN = "1234567890123456";
  assert.equal(getOperatorActor(new Request("http://localhost")), null);
  assert.equal(getOperatorActor(new Request("http://localhost", { headers: { "x-novanusa-operator-token": "wrong" } })), null);
});

test("authorized actor is determined by server, not request actor input", () => {
  process.env.NOVANUSA_OPERATOR_TOKEN = "1234567890123456";
  const request = new Request("http://localhost?actor=attacker", { headers: { "x-novanusa-operator-token": "1234567890123456" } });
  assert.equal(getOperatorActor(request), "local-operator");
});

test("contact without explicit verification is rejected", () => {
  assert.equal(validateVerifiedContact(verifiedProspect({ contactVerificationStatus: "" }), "inst-1").ok, false);
});

test("CONTACT_NEEDS_REVIEW is rejected", () => {
  const result = validateVerifiedContact(verifiedProspect({ contact_status: "CONTACT_NEEDS_REVIEW" }), "inst-1");
  assert.deepEqual(result, { ok: false, code: "CONTACT_NEEDS_REVIEW" });
});

test("verified contact bound to institution is accepted", () => {
  assert.equal(validateVerifiedContact(verifiedProspect(), "inst-1").ok, true);
  assert.equal(validateVerifiedContact(verifiedProspect(), "inst-2").ok, false);
});

test("approval then ready transition is server controlled", () => {
  const initial = createDefaultWorkflowState().draft;
  const drafted = applyDraftTransition(initial, { text: "Approved body", status: "SAVED" }, "local-operator", "t1");
  assert.equal(drafted.ok, true);
  const approved = applyDraftTransition(drafted.draft, { status: "APPROVED" }, "local-operator", "t2");
  assert.equal(approved.ok, true);
  const ready = applyDraftTransition(approved.draft, { status: "READY_TO_SEND" }, "local-operator", "t3");
  assert.equal(ready.ok, true);
});

test("editing an approved draft cancels approval and readiness", () => {
  const current = { ...createDefaultWorkflowState().draft, text: "Old", status: "READY_TO_SEND", approved: true, readyToSend: true, approvedBy: "local-operator", approvedAt: "t1" };
  const changed = applyDraftTransition(current, { text: "New", status: "EDITED" }, "local-operator", "t2");
  assert.equal(changed.ok, true);
  assert.equal(changed.draft.approved, false);
  assert.equal(changed.draft.readyToSend, false);
});

test("client cannot write sent or reserved state", () => {
  const current = createDefaultWorkflowState().draft;
  assert.equal(applyDraftTransition(current, { status: "SENT", sent: true }, "local-operator", "t").ok, false);
});

test("duplicate idempotency reservation does not create a second audit record", async () => {
  const { reserveEmailSend, finalizeEmailSend, getEmailSendHistory } = await import("./email-send-history-store.ts");
  const record = {
    institutionId: "inst-1", sentAt: "t", attemptTimestamp: "t", mode: "test", intendedRecipient: "institution@example.go.id",
    actualRecipient: "operator@example.com", subject: "[TEST REDIRECT] Subject", providerMessageId: null, status: "reserved",
    error: null, idempotencyKey: "same-key", actor: "local-operator", approvalActor: "local-operator",
    approvalTimestamp: "t", provider: "resend", result: "SEND_RESERVED", safeErrorCode: null,
  };
  const firstReservation = reserveEmailSend(record);
  assert.equal(firstReservation.acquired, true);
  assert.equal(reserveEmailSend(record).acquired, false);
  assert.equal(getEmailSendHistory().filter((item) => item.idempotencyKey === "same-key").length, 1);
  const sentAudit = finalizeEmailSend(firstReservation.record.attemptId, { status: "sent", result: "SENT", providerMessageId: "provider-id" });
  assert.equal(sentAudit.providerMessageId, "provider-id");
  assert.equal(sentAudit.result, "SENT");
});

test("Resend success and failure are mapped without real network calls", async () => {
  enableTestMode();
  const success = await sendEmailSafely(testPayload(), async () => new Response(JSON.stringify({ id: "provider-id" }), { status: 200 }));
  const failure = await sendEmailSafely(testPayload(), async () => new Response(JSON.stringify({ message: "sensitive provider detail" }), { status: 422 }));
  assert.equal(success.providerMessageId, "provider-id");
  assert.equal(success.status, "sent");
  assert.equal(failure.status, "failed");
  assert.equal(failure.errorCode, "PROVIDER_REJECTED");
  assert.doesNotMatch(failure.error, /sensitive provider detail/);
});

test("failed reservation is finalized as FAILED audit", async () => {
  const { reserveEmailSend, finalizeEmailSend } = await import("./email-send-history-store.ts");
  const reservation = reserveEmailSend({
    institutionId: "inst-2", sentAt: "t", mode: "test", intendedRecipient: "institution@example.go.id",
    actualRecipient: "operator@example.com", subject: "[TEST REDIRECT] Subject", providerMessageId: null,
    status: "reserved", error: null, idempotencyKey: "failed-key",
  });
  assert.equal(reservation.acquired, true);
  const audit = finalizeEmailSend(reservation.record.attemptId, {
    status: "failed", result: "FAILED", safeErrorCode: "PROVIDER_REJECTED", error: "Safe error",
  });
  assert.equal(audit.result, "FAILED");
  assert.equal(audit.safeErrorCode, "PROVIDER_REJECTED");
});

test("failed attempt permits a new reservation with a new attempt identifier", async () => {
  const { reserveEmailSend, finalizeEmailSend } = await import("./email-send-history-store.ts");
  const record = {
    institutionId: "retry-inst", sentAt: "t1", mode: "test", intendedRecipient: "institution@example.go.id",
    actualRecipient: "operator@example.com", subject: "Subject", providerMessageId: null,
    status: "reserved", error: null, idempotencyKey: "retry-after-failed-key",
  };
  const first = reserveEmailSend(record);
  assert.equal(first.acquired, true);
  finalizeEmailSend(first.record.attemptId, { status: "failed", result: "FAILED" });
  const retry = reserveEmailSend({ ...record, sentAt: "t2" });
  assert.equal(retry.acquired, true);
  assert.notEqual(retry.record.attemptId, first.record.attemptId);
  assert.equal(retry.record.attemptNumber, 2);
});

test("parallel retry after FAILED permits only one active reservation", async () => {
  const { reserveEmailSend, finalizeEmailSend } = await import("./email-send-history-store.ts");
  const record = {
    institutionId: "parallel-inst", sentAt: "t1", mode: "test", intendedRecipient: "institution@example.go.id",
    actualRecipient: "operator@example.com", subject: "Subject", providerMessageId: null,
    status: "reserved", error: null, idempotencyKey: "parallel-retry-key",
  };
  const first = reserveEmailSend(record);
  assert.equal(first.acquired, true);
  finalizeEmailSend(first.record.attemptId, { status: "failed", result: "FAILED" });
  const results = await Promise.all([
    Promise.resolve().then(() => reserveEmailSend({ ...record, sentAt: "t2" })),
    Promise.resolve().then(() => reserveEmailSend({ ...record, sentAt: "t2" })),
  ]);
  assert.equal(results.filter((item) => item.acquired).length, 1);
  assert.equal(results.filter((item) => !item.acquired).length, 1);
});

test("SENT attempt continues to block retry for the same idempotency key", async () => {
  const { reserveEmailSend, finalizeEmailSend } = await import("./email-send-history-store.ts");
  const record = {
    institutionId: "sent-inst", sentAt: "t1", mode: "test", intendedRecipient: "institution@example.go.id",
    actualRecipient: "operator@example.com", subject: "Subject", providerMessageId: null,
    status: "reserved", error: null, idempotencyKey: "sent-retry-key",
  };
  const first = reserveEmailSend(record);
  assert.equal(first.acquired, true);
  finalizeEmailSend(first.record.attemptId, { status: "sent", result: "SENT" });
  const retry = reserveEmailSend({ ...record, sentAt: "t2" });
  assert.equal(retry.acquired, false);
  assert.equal(retry.existing.status, "sent");
});

test("audit trail retains failed attempt and appends retry attempt", async () => {
  const { reserveEmailSend, finalizeEmailSend, getEmailSendHistory } = await import("./email-send-history-store.ts");
  const record = {
    institutionId: "audit-retry-inst", sentAt: "t1", mode: "test", intendedRecipient: "institution@example.go.id",
    actualRecipient: "operator@example.com", subject: "Subject", providerMessageId: null,
    status: "reserved", error: null, idempotencyKey: "audit-retry-key",
  };
  const first = reserveEmailSend(record);
  assert.equal(first.acquired, true);
  finalizeEmailSend(first.record.attemptId, { status: "failed", result: "FAILED" });
  const retry = reserveEmailSend({ ...record, sentAt: "t2" });
  assert.equal(retry.acquired, true);
  const attempts = getEmailSendHistory().filter((item) => item.idempotencyKey === "audit-retry-key");
  assert.equal(attempts.length, 2);
  assert.equal(attempts[0].status, "failed");
  assert.equal(attempts[1].status, "reserved");
  assert.deepEqual(attempts.map((item) => item.attemptNumber), [1, 2]);
});
