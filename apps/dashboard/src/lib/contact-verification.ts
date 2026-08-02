import { createHash } from "node:crypto";
import type { Prospect } from "./institution-data.ts";

export const CONTACT_VERIFICATION_SOURCE = "OFFICIAL_INSTITUTION_WEBSITE" as const;

export type ContactVerificationRecord = {
  verificationId: string;
  institutionId: string;
  email: string;
  sourceUrl: string;
  verificationSource: typeof CONTACT_VERIFICATION_SOURCE;
  status: "VERIFIED";
  verifiedAt: string;
  verifiedBy: string;
  evidenceFingerprint: string;
};

export function normalizeContactEmail(value: string) {
  return value.trim().toLowerCase();
}

export function normalizeContactSourceUrl(value: string): string | null {
  try {
    const url = new URL(value.trim());
    if (url.protocol !== "https:" || url.username || url.password) return null;
    url.hash = "";
    return url.href;
  } catch {
    return null;
  }
}

export function createContactFingerprint(
  institutionId: string,
  email: string,
  sourceUrl: string,
  verificationSource: typeof CONTACT_VERIFICATION_SOURCE,
) {
  const normalizedUrl = normalizeContactSourceUrl(sourceUrl);
  if (!normalizedUrl) return null;
  return createHash("sha256")
    .update([institutionId, normalizeContactEmail(email), normalizedUrl, verificationSource].join("\u001f"), "utf8")
    .digest("hex");
}

export function mergeCanonicalContactVerification(
  prospect: Prospect,
  record: ContactVerificationRecord | null,
): Prospect {
  const unverified = {
    ...prospect,
    contactVerificationStatus: "",
    contactVerifiedAt: "",
    contactVerifiedBy: "",
    contactVerificationSource: "",
  };
  const matchingRecord = getMatchingContactVerification(prospect, record);
  if (!matchingRecord) return unverified;

  return {
    ...unverified,
    contactVerificationStatus: matchingRecord.status,
    contactVerifiedAt: matchingRecord.verifiedAt,
    contactVerifiedBy: matchingRecord.verifiedBy,
    contactVerificationSource: matchingRecord.verificationSource,
  };
}

export function getMatchingContactVerification(
  prospect: Prospect,
  record: ContactVerificationRecord | null,
): ContactVerificationRecord | null {
  if (!record || record.institutionId !== prospect.institution_id || record.status !== "VERIFIED") return null;

  const fingerprint = createContactFingerprint(
    prospect.institution_id,
    prospect.contact_email,
    prospect.contact_source_url,
    record.verificationSource,
  );
  if (
    !fingerprint
    || fingerprint !== record.evidenceFingerprint
    || normalizeContactEmail(prospect.contact_email) !== record.email
    || normalizeContactSourceUrl(prospect.contact_source_url) !== record.sourceUrl
  ) return null;
  return record;
}
