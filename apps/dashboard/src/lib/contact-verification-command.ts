import { randomUUID } from "node:crypto";
import {
  CONTACT_VERIFICATION_SOURCE,
  createContactFingerprint,
  normalizeContactEmail,
  normalizeContactSourceUrl,
  type ContactVerificationRecord,
} from "./contact-verification.ts";
import type { Prospect } from "./institution-data.ts";
import { applyEffectiveContact, resolveEffectiveContact, type ContactOverrideEvent } from "./contact-override.ts";

type Dependencies = {
  getOperatorActor: (request: Request) => string | null;
  findProspectById: (institutionId: string) => Prospect | undefined;
  getContactVerification: (institutionId: string) => ContactVerificationRecord | null;
  saveContactVerification: (record: ContactVerificationRecord) => ContactVerificationRecord;
  getContactOverrideEvents?: (institutionId: string) => ContactOverrideEvent[];
  now?: () => string;
  createId?: () => string;
};

function error(status: number, code: string, message: string) {
  return Response.json({ ok: false, error: { code, message } }, { status });
}

function isExactBody(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const keys = Object.keys(value);
  const expected = ["confirm", "expectedContactFingerprint", "verificationSource"];
  return keys.length === expected.length && keys.every((key) => expected.includes(key));
}

export async function executeContactVerificationCommand(request: Request, institutionId: string, dependencies: Dependencies) {
  const actor = dependencies.getOperatorActor(request);
  if (!actor) return error(401, "UNAUTHORIZED", "Unauthorized.");

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return error(400, "MALFORMED_JSON", "Request body must be valid JSON.");
  }
  if (!isExactBody(body)) return error(400, "INVALID_FIELDS", "Request must contain exactly the documented fields.");
  if (body.confirm !== true) return error(400, "CONFIRMATION_REQUIRED", "Explicit confirmation is required.");
  if (body.verificationSource !== CONTACT_VERIFICATION_SOURCE) {
    return error(400, "UNSUPPORTED_VERIFICATION_SOURCE", "Verification source is not supported.");
  }
  if (typeof body.expectedContactFingerprint !== "string" || !/^[a-f0-9]{64}$/.test(body.expectedContactFingerprint)) {
    return error(400, "INVALID_CONTACT_FINGERPRINT", "Expected contact fingerprint must be a SHA-256 digest.");
  }

  const canonicalProspect = dependencies.findProspectById(institutionId);
  if (!canonicalProspect) return error(404, "INSTITUTION_NOT_FOUND", "Institution not found.");
  const effective = resolveEffectiveContact(canonicalProspect, dependencies.getContactOverrideEvents?.(institutionId) ?? []);
  if (!effective) return error(409, "CONTACT_MISMATCHED", "The rejected contact cannot be verified.");
  const prospect = applyEffectiveContact(canonicalProspect, effective);
  if (prospect.contact_status.trim().toUpperCase() !== "CONTACT_FOUND") {
    return error(409, "CONTACT_STATUS_NOT_VERIFIED", "Contact must have CONTACT_FOUND status.");
  }
  const email = normalizeContactEmail(prospect.contact_email);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return error(409, "CONTACT_EMAIL_INVALID", "Contact email is invalid.");
  const sourceUrl = normalizeContactSourceUrl(prospect.contact_source_url);
  if (!sourceUrl) return error(409, "CONTACT_SOURCE_INVALID", "Contact evidence must be a valid HTTPS URL.");

  const evidenceFingerprint = createContactFingerprint(institutionId, email, sourceUrl, CONTACT_VERIFICATION_SOURCE);
  if (!evidenceFingerprint || evidenceFingerprint !== body.expectedContactFingerprint) {
    return error(409, "CONTACT_CHANGED", "The current contact no longer matches the confirmed contact.");
  }

  const existing = dependencies.getContactVerification(institutionId);
  if (existing?.evidenceFingerprint === evidenceFingerprint) {
    return Response.json({ ok: true, verification: existing, idempotent: true });
  }

  const record: ContactVerificationRecord = {
    verificationId: (dependencies.createId ?? randomUUID)(),
    institutionId,
    email,
    sourceUrl,
    verificationSource: CONTACT_VERIFICATION_SOURCE,
    status: "VERIFIED",
    verifiedAt: (dependencies.now ?? (() => new Date().toISOString()))(),
    verifiedBy: actor,
    evidenceFingerprint,
  };
  try {
    const saved = dependencies.saveContactVerification(record);
    return Response.json({ ok: true, verification: saved, idempotent: saved.verificationId !== record.verificationId });
  } catch {
    return error(500, "PERSISTENCE_FAILED", "Contact verification could not be persisted.");
  }
}
