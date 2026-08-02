/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- Node's native TypeScript runner requires explicit .ts specifiers.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { projectEmailSent } from "./crm-timeline.ts";
import {
  CONTACT_VERIFICATION_SOURCE,
  createContactFingerprint,
  getMatchingContactVerification,
} from "./contact-verification.ts";

test("sent emailSend projects EMAIL_SENT with its canonical sentAt", () => {
  assert.deepEqual(projectEmailSent({ status: "sent", sentAt: "2026-08-02T02:20:37.514Z" }), {
    completed: true,
    timestamp: "2026-08-02T02:20:37.514Z",
  });
});

test("failed and unsent email do not project EMAIL_SENT", () => {
  assert.deepEqual(projectEmailSent({ status: "failed", sentAt: "legacy-time" }), { completed: false, timestamp: null });
  assert.deepEqual(projectEmailSent({ status: "not_sent", sentAt: null }), { completed: false, timestamp: null });
  assert.deepEqual(projectEmailSent({ status: "reserved", sentAt: "legacy-time" }), { completed: false, timestamp: null });
});

test("timeline UI ignores legacy EMAIL_SENT timestamp and preserves manual timestamps", () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "app", "institutions", "[id]", "CommunicationTimeline.tsx"), "utf8");
  assert.match(source, /event\.key === "EMAIL_SENT" \? emailSent\.timestamp/);
  assert.match(source, /manual \? timeline\.eventTimestamps\[event\.key\] \?\? null/);
  assert.doesNotMatch(source, /timeline\.eventTimestamps\.EMAIL_SENT/);
  assert.match(source, /sendTimelineCommandIfActive/);
});

function prospect(overrides = {}) {
  return {
    institution_id: "inst-1", institution_name: "One", institution_display_name: "One", parent_organization: "", work_unit: "",
    province_or_region: "", location_hint: "", target_level: "", send_readiness: "", total_relevant_packages: 0, total_pagu: 0,
    months_found: "", relevant_categories: "", example_package_names: "", evidence_status: "", spse_status: "", contact_status: "CONTACT_FOUND",
    outreach_status: "", contact_email: "contact@example.go.id", official_website: "https://example.go.id",
    contact_source_url: "https://example.go.id/contact", contact_phone: "", contact_whatsapp: "", contact_person: "", contact_role: "",
    contact_notes: "", contactVerificationStatus: "", contactVerifiedAt: "", contactVerifiedBy: "", contactVerificationSource: "",
    ...overrides,
  };
}

function verification(current = prospect()) {
  return {
    verificationId: "verification-1",
    institutionId: current.institution_id,
    email: current.contact_email,
    sourceUrl: current.contact_source_url,
    verificationSource: CONTACT_VERIFICATION_SOURCE,
    status: "VERIFIED",
    verifiedAt: "2026-08-02T01:00:00.000Z",
    verifiedBy: "local-operator",
    evidenceFingerprint: createContactFingerprint(current.institution_id, current.contact_email, current.contact_source_url, CONTACT_VERIFICATION_SOURCE),
  };
}

test("only matching persisted verification hydrates the VERIFIED presentation", () => {
  const current = prospect();
  const record = verification(current);
  assert.deepEqual(getMatchingContactVerification(current, record), record);
  assert.equal(getMatchingContactVerification(prospect({ contact_email: "changed@example.go.id" }), record), null);
  assert.equal(getMatchingContactVerification(prospect({ contact_source_url: "https://example.go.id/other" }), record), null);
});

test("institution page reads canonical verification and passes only its matching state", () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "app", "institutions", "[id]", "page.tsx"), "utf8");
  assert.match(source, /getMatchingContactVerification\(institution, getContactVerification\(id\)\)/);
  assert.match(source, /initialVerification=\{persistedVerification\}/);
  assert.match(source, /dynamic = "force-dynamic"/);
});

test("verification UI renders persisted VERIFIED state and hydrates from POST success", () => {
  const source = fs.readFileSync(path.join(process.cwd(), "src", "app", "institutions", "[id]", "ContactVerificationAction.tsx"), "utf8");
  assert.match(source, /useState<ContactVerificationRecord \| null>\(props\.initialVerification\)/);
  assert.match(source, /setVerification\(payload\.verification\)/);
  assert.match(source, /if \(verification\)/);
  assert.match(source, />VERIFIED</);
  assert.match(source, /verification\.verifiedAt/);
  assert.match(source, /verification\.verifiedBy/);
  assert.match(source, /verification\.verificationSource/);
  assert.match(source, /type="checkbox"/);
  assert.match(source, />Verifikasi Kontak</);
});
