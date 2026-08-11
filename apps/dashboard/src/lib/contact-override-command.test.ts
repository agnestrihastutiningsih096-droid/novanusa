/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import assert from "node:assert/strict";
import test from "node:test";
import { CONTACT_VERIFICATION_SOURCE, createContactFingerprint, mergeCanonicalContactVerification } from "./contact-verification.ts";
import { executeContactVerificationCommand } from "./contact-verification-command.ts";
import { executeContactMismatchCommand, executeContactReplacementCommand } from "./contact-override-command.ts";
import { applyEffectiveContact, resolveEffectiveContact } from "./contact-override.ts";
import { validateVerifiedContact } from "./institution-data.ts";

const now = "2026-08-10T01:00:00.000Z";
const prospect = (overrides = {}) => ({ institution_id: "inst-1", institution_name: "One", institution_display_name: "One", parent_organization: "", work_unit: "", province_or_region: "", location_hint: "", target_level: "", send_readiness: "", total_relevant_packages: 0, total_pagu: 0, months_found: "", relevant_categories: "", example_package_names: "", evidence_status: "", spse_status: "", outreach_status: "", contact_status: "CONTACT_FOUND", contact_email: "a@example.go.id", official_website: "", contact_source_url: "https://example.go.id/a", contact_phone: "", contact_whatsapp: "", contact_person: "", contact_role: "", contact_notes: "", contactVerificationStatus: "", contactVerifiedAt: "", contactVerifiedBy: "", contactVerificationSource: "", ...overrides });
const request = (path, body, auth = true) => new Request(`http://localhost/${path}`, { method: "POST", headers: auth ? { "x-operator": "yes" } : {}, body: JSON.stringify(body) });
const canonicalFingerprint = () => createContactFingerprint("inst-1", "a@example.go.id", "https://example.go.id/a", CONTACT_VERIFICATION_SOURCE);

function harness() {
  const events = []; let writes = 0; let sequence = 0; const current = prospect();
  const deps = { getOperatorActor: (req) => req.headers.get("x-operator") ? "server-actor" : null, findProspectById: (id) => id === "inst-1" ? current : undefined, getEvents: (id) => events.filter((event) => event.institutionId === id), appendEvent: (event) => { writes += 1; events.push(event); return event; }, now: () => now, createId: () => `id-${++sequence}` };
  return { events, deps, get writes() { return writes; } };
}

const mismatchBody = (fingerprint = canonicalFingerprint()) => ({ expectedContactFingerprint: fingerprint, reasonCode: "NOT_FOUND_ON_OFFICIAL_SOURCE", evidenceUrl: "https://example.go.id/directory" });

test("mismatch is authenticated, exact, server-owned, and stale fingerprints cause no write", async () => {
  for (const [body, auth] of [[mismatchBody(), false], [{ ...mismatchBody(), actor: "attacker" }, true], [{ ...mismatchBody(), expectedContactFingerprint: "0".repeat(64) }, true]]) {
    const h = harness(); const response = await executeContactMismatchCommand(request("mismatch", body, auth), "inst-1", h.deps);
    assert.notEqual(response.status, 200); assert.equal(h.writes, 0);
  }
  const h = harness(); const response = await executeContactMismatchCommand(request("mismatch", mismatchBody()), "inst-1", h.deps); const payload = await response.json();
  assert.equal(response.status, 200); assert.equal(payload.mismatch.actor, "server-actor"); assert.equal(payload.mismatch.createdAt, now); assert.equal(resolveEffectiveContact(prospect(), h.events), null);
});

test("replacement validates HTTPS, email, confirmation, parent, and rejected identity", async () => {
  const invalidBodies = [
    { parentMismatchId: "id-1", email: "bad", confirmEmail: "bad", evidenceUrl: "https://example.go.id/b" },
    { parentMismatchId: "id-1", email: "b@example.go.id", confirmEmail: "b@example.go.id", evidenceUrl: "http://example.go.id/b" },
    { parentMismatchId: "id-1", email: "a@example.go.id", confirmEmail: "a@example.go.id", evidenceUrl: "https://example.go.id/a" },
  ];
  for (const body of invalidBodies) { const h = harness(); await executeContactMismatchCommand(request("mismatch", mismatchBody()), "inst-1", h.deps); const response = await executeContactReplacementCommand(request("replacement", body), "inst-1", h.deps); assert.notEqual(response.status, 200); assert.equal(h.events.length, 1); }
});

test("replacement starts unverified and canonical verification cannot authorize it", async () => {
  const h = harness(); await executeContactMismatchCommand(request("mismatch", mismatchBody()), "inst-1", h.deps);
  const response = await executeContactReplacementCommand(request("replacement", { parentMismatchId: "id-1", email: "b@example.go.id", confirmEmail: "B@example.go.id", evidenceUrl: "https://example.go.id/b" }), "inst-1", h.deps); const payload = await response.json();
  assert.equal(payload.verification, null); const effective = resolveEffectiveContact(prospect(), h.events); assert.equal(effective.email, "b@example.go.id");
  const canonicalRecord = { verificationId: "v-a", institutionId: "inst-1", email: "a@example.go.id", sourceUrl: "https://example.go.id/a", verificationSource: CONTACT_VERIFICATION_SOURCE, status: "VERIFIED", verifiedAt: now, verifiedBy: "actor", evidenceFingerprint: canonicalFingerprint() };
  assert.equal(validateVerifiedContact(mergeCanonicalContactVerification(applyEffectiveContact(prospect(), effective), canonicalRecord), "inst-1").ok, false);
});

test("fresh verification binds to current replacement and cross-institution substitution fails", async () => {
  const h = harness(); await executeContactMismatchCommand(request("mismatch", mismatchBody()), "inst-1", h.deps); await executeContactReplacementCommand(request("replacement", { parentMismatchId: "id-1", email: "b@example.go.id", confirmEmail: "b@example.go.id", evidenceUrl: "https://example.go.id/b" }), "inst-1", h.deps);
  let verification = null; const effective = resolveEffectiveContact(prospect(), h.events);
  const response = await executeContactVerificationCommand(request("verify", { confirm: true, expectedContactFingerprint: effective.fingerprint, verificationSource: CONTACT_VERIFICATION_SOURCE }), "inst-1", { getOperatorActor: h.deps.getOperatorActor, findProspectById: h.deps.findProspectById, getContactOverrideEvents: h.deps.getEvents, getContactVerification: () => verification, saveContactVerification: (record) => (verification = record), now: () => now, createId: () => "verification-b" });
  assert.equal(response.status, 200); const verified = mergeCanonicalContactVerification(applyEffectiveContact(prospect(), effective), verification); assert.equal(validateVerifiedContact(verified, "inst-1").ok, true); assert.equal(validateVerifiedContact(verified, "inst-2").ok, false);
});

test("A rejected, B replaced/rejected, C replaced preserves history and invalidates B verification", async () => {
  const h = harness(); await executeContactMismatchCommand(request("mismatch", mismatchBody()), "inst-1", h.deps); await executeContactReplacementCommand(request("replacement", { parentMismatchId: "id-1", email: "b@example.go.id", confirmEmail: "b@example.go.id", evidenceUrl: "https://example.go.id/b" }), "inst-1", h.deps);
  const b = resolveEffectiveContact(prospect(), h.events); const bVerification = { verificationId: "v-b", institutionId: "inst-1", email: b.email, sourceUrl: b.sourceUrl, verificationSource: CONTACT_VERIFICATION_SOURCE, status: "VERIFIED", verifiedAt: now, verifiedBy: "actor", evidenceFingerprint: b.fingerprint };
  await executeContactMismatchCommand(request("mismatch", mismatchBody(b.fingerprint)), "inst-1", h.deps); await executeContactReplacementCommand(request("replacement", { parentMismatchId: "id-3", email: "c@example.go.id", confirmEmail: "c@example.go.id", evidenceUrl: "https://example.go.id/c" }), "inst-1", h.deps);
  const c = resolveEffectiveContact(prospect(), h.events); assert.equal(c.email, "c@example.go.id"); assert.equal(h.events.length, 4); assert.deepEqual(h.events.map((event) => event.type), ["MISMATCH", "REPLACEMENT", "MISMATCH", "REPLACEMENT"]); assert.equal(validateVerifiedContact(mergeCanonicalContactVerification(applyEffectiveContact(prospect(), c), bVerification), "inst-1").ok, false);
});

test("send route resolves effective contact before verification and retains test redirect sender call", async () => {
  const source = await import("node:fs").then((fs) => fs.readFileSync(new URL("../app/api/institutions/[id]/send-email/route.ts", import.meta.url), "utf8"));
  assert.match(source, /resolveEffectiveContact\(institution, getContactOverrideEvents\(id\)\)/); assert.match(source, /mergeCanonicalContactVerification\(effectiveInstitution/); assert.match(source, /intendedRecipient: contact\.snapshot\.email/); assert.match(source, /sendEmailSafely\([\s\S]*to: contact\.snapshot\.email/);
});
