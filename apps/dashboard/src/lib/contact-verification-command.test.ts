/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import test from "node:test";
import {
  CONTACT_VERIFICATION_SOURCE,
  createContactFingerprint,
  mergeCanonicalContactVerification,
} from "./contact-verification.ts";
import { executeContactVerificationCommand } from "./contact-verification-command.ts";
import { validateVerifiedContact } from "./institution-data.ts";

const fixedTime = "2026-08-02T10:00:00.000Z";
const fixedId = "verification-1";

function prospect(overrides = {}) {
  return {
    institution_id: "inst-1",
    institution_name: "Institution One",
    institution_display_name: "Institution One",
    parent_organization: "", work_unit: "", province_or_region: "", location_hint: "", target_level: "",
    send_readiness: "", total_relevant_packages: 0, total_pagu: 0, months_found: "", relevant_categories: "",
    example_package_names: "", evidence_status: "", spse_status: "", outreach_status: "",
    contact_status: "CONTACT_FOUND",
    contact_email: "Contact@Example.go.id ",
    official_website: "https://example.go.id",
    contact_source_url: "https://example.go.id/contact#team",
    contact_phone: "", contact_whatsapp: "", contact_person: "", contact_role: "", contact_notes: "",
    contactVerificationStatus: "", contactVerifiedAt: "", contactVerifiedBy: "", contactVerificationSource: "",
    ...overrides,
  };
}

function fingerprint(value = prospect()) {
  return createContactFingerprint(value.institution_id, value.contact_email, value.contact_source_url, CONTACT_VERIFICATION_SOURCE);
}

function request(body, authenticated = true) {
  return new Request("http://localhost/api/institutions/inst-1/contact-verification", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(authenticated ? { "x-test-operator": "yes" } : {}) },
    body: JSON.stringify(body),
  });
}

function validBody(value = prospect()) {
  return { confirm: true, expectedContactFingerprint: fingerprint(value) ?? "0".repeat(64), verificationSource: CONTACT_VERIFICATION_SOURCE };
}

async function run(body, options = {}) {
  const currentProspect = options.prospect ?? prospect();
  let stored = options.existing ?? null;
  let saves = 0;
  const response = await executeContactVerificationCommand(request(body, options.authenticated !== false), currentProspect.institution_id, {
    getOperatorActor: (incoming) => incoming.headers.get("x-test-operator") === "yes" ? "server-operator" : null,
    findProspectById: (id) => id === currentProspect.institution_id ? currentProspect : undefined,
    getContactVerification: () => stored,
    saveContactVerification(record) {
      saves += 1;
      if (options.persistenceFailure) throw new Error("disk unavailable");
      stored = record;
      return record;
    },
    now: () => fixedTime,
    createId: () => fixedId,
  });
  return { response, payload: await response.json(), getStored: () => stored, saves };
}

test("unauthorized request causes no write", async () => {
  const result = await run(validBody(), { authenticated: false });
  assert.equal(result.response.status, 401);
  assert.equal(result.payload.error.code, "UNAUTHORIZED");
  assert.equal(result.saves, 0);
});

test("request requires exactly the documented non-null fields", async () => {
  const valid = validBody();
  for (const body of [
    {}, null,
    { ...valid, unknown: true },
    { ...valid, verifiedAt: fixedTime },
    { ...valid, contactEmail: "attacker@example.com" },
    { confirm: true, verificationSource: CONTACT_VERIFICATION_SOURCE },
    { ...valid, expectedContactFingerprint: null },
    { ...valid, expectedContactFingerprint: "" },
    { ...valid, confirm: null },
  ]) {
    const result = await run(body);
    assert.equal(result.response.status, 400);
    assert.equal(result.saves, 0);
  }
});

test("invalid contact status, email, and HTTPS evidence fail closed", async () => {
  for (const invalid of [
    prospect({ contact_status: "CONTACT_NEEDS_REVIEW" }),
    prospect({ contact_email: "invalid" }),
    prospect({ contact_source_url: "http://example.go.id/contact" }),
    prospect({ contact_source_url: "not-a-url" }),
  ]) {
    const result = await run(validBody(invalid), { prospect: invalid });
    assert.equal(result.response.status, 409);
    assert.equal(result.saves, 0);
  }
});

test("unsupported source and stale fingerprint are rejected", async () => {
  const unsupported = await run({ ...validBody(), verificationSource: "OPERATOR_ASSERTION" });
  assert.equal(unsupported.payload.error.code, "UNSUPPORTED_VERIFICATION_SOURCE");
  const stale = await run({ ...validBody(), expectedContactFingerprint: "0".repeat(64) });
  assert.equal(stale.response.status, 409);
  assert.equal(stale.payload.error.code, "CONTACT_CHANGED");
  assert.equal(stale.saves, 0);
});

test("successful verification uses server-owned identity, time, status, and evidence", async () => {
  const result = await run(validBody());
  assert.equal(result.response.status, 200);
  assert.equal(result.payload.idempotent, false);
  assert.deepEqual(result.payload.verification, {
    verificationId: fixedId,
    institutionId: "inst-1",
    email: "contact@example.go.id",
    sourceUrl: "https://example.go.id/contact",
    verificationSource: CONTACT_VERIFICATION_SOURCE,
    status: "VERIFIED",
    verifiedAt: fixedTime,
    verifiedBy: "server-operator",
    evidenceFingerprint: fingerprint(),
  });
  assert.equal(result.saves, 1);
});

test("identical retry returns the original record unchanged", async () => {
  const first = await run(validBody());
  const original = first.getStored();
  const retry = await run(validBody(), { existing: original });
  assert.equal(retry.payload.idempotent, true);
  assert.deepEqual(retry.payload.verification, original);
  assert.equal(retry.payload.verification.verificationId, fixedId);
  assert.equal(retry.payload.verification.verifiedAt, fixedTime);
  assert.equal(retry.saves, 0);
});

test("institution isolation and changed contacts do not inherit verification", async () => {
  const created = await run(validBody());
  const record = created.getStored();
  const other = prospect({ institution_id: "inst-2" });
  const changed = prospect({ contact_email: "changed@example.go.id" });
  assert.equal(validateVerifiedContact(mergeCanonicalContactVerification(other, record), "inst-2").ok, false);
  assert.equal(validateVerifiedContact(mergeCanonicalContactVerification(changed, record), "inst-1").ok, false);
});

test("persistence failure fails closed", async () => {
  const result = await run(validBody(), { persistenceFailure: true });
  assert.equal(result.response.status, 500);
  assert.equal(result.payload.error.code, "PERSISTENCE_FAILED");
  assert.equal(result.saves, 1);
  assert.equal(result.getStored(), null);
});

test("send-email contact gate blocks without canonical verification and passes with an exact match", async () => {
  const current = prospect({ contactVerificationStatus: "VERIFIED", contactVerifiedAt: "csv-time", contactVerifiedBy: "csv", contactVerificationSource: CONTACT_VERIFICATION_SOURCE });
  const withoutCanonical = validateVerifiedContact(mergeCanonicalContactVerification(current, null), "inst-1");
  assert.deepEqual(withoutCanonical, { ok: false, code: "CONTACT_VERIFICATION_MISSING" });

  const created = await run(validBody(current), { prospect: current });
  const withCanonical = validateVerifiedContact(mergeCanonicalContactVerification(current, created.getStored()), "inst-1");
  assert.equal(withCanonical.ok, true);
  assert.equal(withCanonical.snapshot.verifiedAt, fixedTime);
});
