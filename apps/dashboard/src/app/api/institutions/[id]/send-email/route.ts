import { createHash } from "crypto";
import { NextResponse } from "next/server";
import { mergeCanonicalContactVerification } from "@/lib/contact-verification";
import { getContactVerification } from "@/lib/contact-verification-store";
import { applyEffectiveContact, resolveEffectiveContact } from "@/lib/contact-override";
import { getContactOverrideEvents } from "@/lib/contact-override-store";
import { finalizeEmailSend, reserveEmailSend, type EmailSendHistoryRecord } from "@/lib/email-send-history-store";
import { getEmailSendMode, getOperatorActor, getTestRecipient, sendEmailSafely } from "@/lib/email-sender";
import { findProspectById, validateVerifiedContact } from "@/lib/institution-data";
import { getWorkflowState, saveWorkflowState } from "@/lib/workflow-state-store";

type RouteContext = { params: Promise<{ id: string }> };

const subject = "Informasi Rekomendasi Produk Berdasarkan Rencana Pengadaan SiRUP";

function responseError(message: string, status: number, code: string) {
  return NextResponse.json({ ok: false, error: message, code, mode: getEmailSendMode() }, { status });
}

function createEmailIdempotencyKey(institutionId: string, draftText: string, mode: string, actualRecipient: string) {
  const digest = createHash("sha256").update(draftText, "utf8").digest("hex");
  return createHash("sha256").update([institutionId, digest, mode, actualRecipient.toLowerCase()].join("\u001f"), "utf8").digest("hex");
}

export async function GET(request: Request) {
  if (!getOperatorActor(request)) return responseError("Unauthorized.", 401, "UNAUTHORIZED");
  const mode = getEmailSendMode();
  const testRecipient = mode === "test" ? getTestRecipient() : null;
  return NextResponse.json({
    mode,
    subject,
    actualRecipient: testRecipient?.errorCode ? "" : testRecipient?.recipient ?? "",
    configurationError: testRecipient?.errorCode ?? (mode === "real" ? "REAL_MODE_DISABLED" : null),
  });
}

export async function POST(request: Request, context: RouteContext) {
  const actor = getOperatorActor(request);
  if (!actor) return responseError("Unauthorized.", 401, "UNAUTHORIZED");

  try {
    const mode = getEmailSendMode();
    if (mode === "real") return responseError("Real email mode is temporarily disabled.", 409, "REAL_MODE_DISABLED");
    const testRecipient = mode === "test" ? getTestRecipient() : { recipient: "mock:no-real-recipient", errorCode: null };
    if (testRecipient.errorCode) return responseError("Test recipient configuration is not permitted.", 503, testRecipient.errorCode);

    const { id } = await context.params;
    const body = (await request.json().catch(() => ({}))) as { confirm?: boolean };
    if (body.confirm !== true) return responseError("Send confirmation is required.", 400, "CONFIRMATION_REQUIRED");

    const institution = findProspectById(id);
    if (!institution) return responseError("Institution not found.", 404, "INSTITUTION_NOT_FOUND");
    const effectiveContact = resolveEffectiveContact(institution, getContactOverrideEvents(id));
    if (!effectiveContact) return responseError("Current contact was rejected and requires a replacement.", 409, "CONTACT_MISMATCHED");
    const effectiveInstitution = applyEffectiveContact(institution, effectiveContact);
    const verifiedInstitution = mergeCanonicalContactVerification(effectiveInstitution, getContactVerification(id));
    const contact = validateVerifiedContact(verifiedInstitution, id);
    if (!contact.ok) return responseError("Verified institutional contact is required.", 409, contact.code);

    const state = getWorkflowState(id);
    const draftText = state.draft.text.trim();
    if (!draftText) return responseError("Approved draft text is required.", 409, "DRAFT_REQUIRED");
    if (!state.draft.approved || !state.draft.approvedBy || !state.draft.approvedAt) {
      return responseError("Server-side approval is required.", 409, "APPROVAL_REQUIRED");
    }
    if (!state.draft.readyToSend || state.draft.status !== "READY_TO_SEND") {
      return responseError("Draft must be Ready to Send.", 409, "READY_TO_SEND_REQUIRED");
    }

    const actualRecipient = testRecipient.recipient;
    const idempotencyKey = createEmailIdempotencyKey(id, draftText, mode, actualRecipient);
    const attemptTimestamp = new Date().toISOString();
    const auditBase: EmailSendHistoryRecord = {
      institutionId: id,
      sentAt: attemptTimestamp,
      attemptTimestamp,
      mode,
      intendedRecipient: contact.snapshot.email,
      actualRecipient,
      subject: mode === "test" ? `[TEST REDIRECT] ${subject}` : subject,
      providerMessageId: null,
      status: "reserved",
      error: null,
      actor,
      approvalActor: state.draft.approvedBy,
      approvalTimestamp: state.draft.approvedAt,
      contactVerification: contact.snapshot,
      idempotencyKey,
      provider: mode === "test" ? "resend" : "mock",
      result: "SEND_RESERVED",
      safeErrorCode: null,
    };
    const reservation = reserveEmailSend(auditBase);
    if (!reservation.acquired) {
      const existing = reservation.existing;
      return NextResponse.json(
        { ok: existing?.status === "sent", duplicate: true, code: "DUPLICATE_SEND_PREVENTED", mode, result: existing ?? null },
        { status: existing?.status === "sent" ? 200 : 409 },
      );
    }
    const attemptId = reservation.record.attemptId;
    if (!attemptId) return responseError("Email reservation is invalid.", 500, "RESERVATION_INVALID");

    saveWorkflowState(id, {
      draft: { reviewStatus: "Send Reserved" },
      emailSend: {
        sentAt: null, mode, intendedRecipient: contact.snapshot.email, actualRecipient, subject,
        status: "reserved", idempotencyKey, providerMessageId: null, error: null,
      },
    });

    const result = await sendEmailSafely({
      to: contact.snapshot.email,
      subject,
      body: draftText,
      metadata: { institutionId: id, institutionName: institution.institution_name },
    });
    const completedAt = new Date().toISOString();
    const success = result.status === "sent";
    const audit = finalizeEmailSend(attemptId, {
      sentAt: completedAt,
      status: success ? "sent" : "failed",
      result: success ? "SENT" : "FAILED",
      providerMessageId: result.providerMessageId,
      safeErrorCode: result.errorCode,
      error: result.error,
      actualRecipient: result.actualRecipient,
      subject: result.subject,
    });

    const nextState = saveWorkflowState(id, {
      draft: {
        status: success ? "SENT" : "READY_TO_SEND",
        reviewStatus: success ? "Sent" : "Failed",
        sent: success,
        readyToSend: !success,
        updatedAt: completedAt,
      },
      emailSend: {
        sentAt: completedAt,
        mode,
        intendedRecipient: result.intendedRecipient,
        actualRecipient: result.actualRecipient,
        subject: result.subject,
        status: success ? "sent" : "failed",
        idempotencyKey,
        providerMessageId: result.providerMessageId,
        error: result.error,
      },
    });

    if (!success) return NextResponse.json({ ok: false, code: result.errorCode, mode, state: nextState, audit }, { status: 502 });
    return NextResponse.json({ ok: true, mode, result, state: nextState, audit });
  } catch {
    return responseError("Unexpected email send error.", 500, "SEND_INTERNAL_ERROR");
  }
}
