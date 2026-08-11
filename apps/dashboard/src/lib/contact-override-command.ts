import { randomUUID } from "node:crypto";
import { CONTACT_VERIFICATION_SOURCE, createContactFingerprint, normalizeContactEmail, normalizeContactSourceUrl } from "./contact-verification.ts";
import { CONTACT_MISMATCH_REASON_CODES, getCurrentOpenMismatch, resolveEffectiveContact, type ContactMismatchEvent, type ContactOverrideEvent, type ContactReplacementEvent } from "./contact-override.ts";
import type { Prospect } from "./institution-data.ts";

type Dependencies = { getOperatorActor: (request: Request) => string | null; findProspectById: (id: string) => Prospect | undefined; getEvents: (id: string) => ContactOverrideEvent[]; appendEvent: (event: ContactOverrideEvent) => ContactOverrideEvent; now?: () => string; createId?: () => string };
const failure = (status: number, code: string, message: string) => Response.json({ ok: false, error: { code, message } }, { status });
const ownObject = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === "object" && !Array.isArray(value));
const exactKeys = (body: Record<string, unknown>, required: string[], optional: string[] = []) => required.every((key) => Object.hasOwn(body, key)) && Object.keys(body).every((key) => required.includes(key) || optional.includes(key));
const validEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

async function bodyOf(request: Request) { try { return await request.json() as unknown; } catch { return undefined; } }

export async function executeContactMismatchCommand(request: Request, institutionId: string, dependencies: Dependencies) {
  const actor = dependencies.getOperatorActor(request); if (!actor) return failure(401, "UNAUTHORIZED", "Unauthorized.");
  const body = await bodyOf(request); if (!ownObject(body)) return failure(400, "MALFORMED_JSON", "Request body must be an object.");
  if (!exactKeys(body, ["expectedContactFingerprint", "reasonCode", "evidenceUrl"], ["reasonDetail", "observedEmail"])) return failure(400, "INVALID_FIELDS", "Request contains unsupported or missing fields.");
  if (typeof body.expectedContactFingerprint !== "string" || !/^[a-f0-9]{64}$/.test(body.expectedContactFingerprint)) return failure(400, "INVALID_CONTACT_FINGERPRINT", "Invalid contact fingerprint.");
  if (typeof body.reasonCode !== "string" || !CONTACT_MISMATCH_REASON_CODES.includes(body.reasonCode as never)) return failure(400, "INVALID_REASON_CODE", "A supported reason code is required.");
  const evidenceUrl = typeof body.evidenceUrl === "string" ? normalizeContactSourceUrl(body.evidenceUrl) : null; if (!evidenceUrl) return failure(400, "INVALID_EVIDENCE_URL", "Evidence must be a valid HTTPS URL.");
  if (body.reasonDetail !== undefined && (typeof body.reasonDetail !== "string" || !body.reasonDetail.trim() || body.reasonDetail.length > 500)) return failure(400, "INVALID_REASON_DETAIL", "Reason detail is invalid.");
  const observedEmail = body.observedEmail === undefined || body.observedEmail === "" ? undefined : typeof body.observedEmail === "string" ? normalizeContactEmail(body.observedEmail) : "";
  if (observedEmail !== undefined && !validEmail(observedEmail)) return failure(400, "INVALID_OBSERVED_EMAIL", "Observed email is invalid.");
  const prospect = dependencies.findProspectById(institutionId); if (!prospect) return failure(404, "INSTITUTION_NOT_FOUND", "Institution not found.");
  const effective = resolveEffectiveContact(prospect, dependencies.getEvents(institutionId));
  if (!effective || effective.institutionId !== institutionId || effective.fingerprint !== body.expectedContactFingerprint) return failure(409, "CONTACT_CHANGED", "The current effective contact no longer matches.");
  const event: ContactMismatchEvent = { type: "MISMATCH", mismatchId: (dependencies.createId ?? randomUUID)(), institutionId, rejectedEmail: effective.email, rejectedSourceUrl: effective.sourceUrl, rejectedFingerprint: effective.fingerprint, reasonCode: body.reasonCode as ContactMismatchEvent["reasonCode"], ...(body.reasonDetail ? { reasonDetail: body.reasonDetail.trim() } : {}), evidenceUrl, ...(observedEmail ? { observedEmail } : {}), actor, createdAt: (dependencies.now ?? (() => new Date().toISOString()))() };
  try { return Response.json({ ok: true, mismatch: dependencies.appendEvent(event) }); } catch { return failure(500, "PERSISTENCE_FAILED", "Mismatch could not be persisted."); }
}

export async function executeContactReplacementCommand(request: Request, institutionId: string, dependencies: Dependencies) {
  const actor = dependencies.getOperatorActor(request); if (!actor) return failure(401, "UNAUTHORIZED", "Unauthorized.");
  const body = await bodyOf(request); if (!ownObject(body)) return failure(400, "MALFORMED_JSON", "Request body must be an object.");
  if (!exactKeys(body, ["parentMismatchId", "email", "confirmEmail", "evidenceUrl"])) return failure(400, "INVALID_FIELDS", "Request must contain exactly the documented fields.");
  const email = typeof body.email === "string" ? normalizeContactEmail(body.email) : ""; const confirmEmail = typeof body.confirmEmail === "string" ? normalizeContactEmail(body.confirmEmail) : "";
  if (!validEmail(email)) return failure(400, "INVALID_EMAIL", "Replacement email is invalid."); if (email !== confirmEmail) return failure(400, "EMAIL_CONFIRMATION_MISMATCH", "Replacement email confirmation does not match.");
  const evidenceUrl = typeof body.evidenceUrl === "string" ? normalizeContactSourceUrl(body.evidenceUrl) : null; if (!evidenceUrl) return failure(400, "INVALID_EVIDENCE_URL", "Evidence must be a valid HTTPS URL.");
  const prospect = dependencies.findProspectById(institutionId); if (!prospect) return failure(404, "INSTITUTION_NOT_FOUND", "Institution not found.");
  const events = dependencies.getEvents(institutionId); const mismatch = getCurrentOpenMismatch(events, institutionId);
  if (!mismatch || typeof body.parentMismatchId !== "string" || mismatch.mismatchId !== body.parentMismatchId || mismatch.institutionId !== institutionId) return failure(409, "MISMATCH_CHANGED", "The current mismatch no longer matches.");
  if (email === mismatch.rejectedEmail) return failure(409, "REPLACEMENT_EQUALS_REJECTED", "Replacement must differ from the rejected contact.");
  const fingerprint = createContactFingerprint(institutionId, email, evidenceUrl, CONTACT_VERIFICATION_SOURCE); if (!fingerprint) return failure(400, "INVALID_EVIDENCE_URL", "Evidence must be valid.");
  const event: ContactReplacementEvent = { type: "REPLACEMENT", replacementId: (dependencies.createId ?? randomUUID)(), institutionId, parentMismatchId: mismatch.mismatchId, email, evidenceUrl, fingerprint, actor, createdAt: (dependencies.now ?? (() => new Date().toISOString()))() };
  try { return Response.json({ ok: true, replacement: dependencies.appendEvent(event), verification: null }); } catch { return failure(500, "PERSISTENCE_FAILED", "Replacement could not be persisted."); }
}
