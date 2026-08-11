import type { Prospect } from "./institution-data.ts";
import { CONTACT_VERIFICATION_SOURCE, createContactFingerprint, normalizeContactEmail, normalizeContactSourceUrl } from "./contact-verification.ts";

export const CONTACT_MISMATCH_REASON_CODES = ["NOT_FOUND_ON_OFFICIAL_SOURCE", "EMAIL_DIFFERS_FROM_OFFICIAL_SOURCE", "CONTACT_OBSOLETE", "OTHER"] as const;
export type ContactMismatchReasonCode = typeof CONTACT_MISMATCH_REASON_CODES[number];

export type ContactMismatchEvent = {
  type: "MISMATCH"; mismatchId: string; institutionId: string; rejectedEmail: string;
  rejectedSourceUrl: string; rejectedFingerprint: string; reasonCode: ContactMismatchReasonCode;
  reasonDetail?: string; evidenceUrl: string; observedEmail?: string; actor: string; createdAt: string;
};

export type ContactReplacementEvent = {
  type: "REPLACEMENT"; replacementId: string; institutionId: string; parentMismatchId: string;
  email: string; evidenceUrl: string; fingerprint: string; actor: string; createdAt: string;
};

export type ContactOverrideEvent = ContactMismatchEvent | ContactReplacementEvent;
export type EffectiveContact = { institutionId: string; email: string; sourceUrl: string; fingerprint: string; kind: "CANONICAL" | "REPLACEMENT"; replacementId?: string };

export function resolveEffectiveContact(prospect: Prospect, events: ContactOverrideEvent[]): EffectiveContact | null {
  const scoped = events.filter((event) => event.institutionId === prospect.institution_id);
  const canonicalUrl = normalizeContactSourceUrl(prospect.contact_source_url);
  const canonicalFingerprint = canonicalUrl ? createContactFingerprint(prospect.institution_id, prospect.contact_email, canonicalUrl, CONTACT_VERIFICATION_SOURCE) : null;
  let effective: EffectiveContact | null = canonicalFingerprint && canonicalUrl ? { institutionId: prospect.institution_id, email: normalizeContactEmail(prospect.contact_email), sourceUrl: canonicalUrl, fingerprint: canonicalFingerprint, kind: "CANONICAL" } : null;
  let awaitingMismatchId: string | null = null;

  for (const event of scoped) {
    if (event.type === "MISMATCH") {
      if (effective?.fingerprint === event.rejectedFingerprint) {
        effective = null;
        awaitingMismatchId = event.mismatchId;
      }
    } else if (!effective && awaitingMismatchId === event.parentMismatchId) {
      effective = { institutionId: event.institutionId, email: event.email, sourceUrl: event.evidenceUrl, fingerprint: event.fingerprint, kind: "REPLACEMENT", replacementId: event.replacementId };
      awaitingMismatchId = null;
    }
  }
  return effective;
}

export function applyEffectiveContact(prospect: Prospect, effective: EffectiveContact): Prospect {
  return { ...prospect, contact_status: effective.kind === "REPLACEMENT" ? "CONTACT_FOUND" : prospect.contact_status, contact_email: effective.email, contact_source_url: effective.sourceUrl };
}

export function getCurrentOpenMismatch(events: ContactOverrideEvent[], institutionId: string) {
  const scoped = events.filter((event) => event.institutionId === institutionId);
  for (let index = scoped.length - 1; index >= 0; index -= 1) {
    const event = scoped[index];
    if (event.type === "MISMATCH") {
      const hasReplacement = scoped.slice(index + 1).some((candidate) => candidate.type === "REPLACEMENT" && candidate.parentMismatchId === event.mismatchId);
      return hasReplacement ? null : event;
    }
  }
  return null;
}
