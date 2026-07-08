import { NextResponse } from "next/server";
import { appendEmailSendHistory } from "@/lib/email-send-history-store";
import { getEmailSendMode, sendEmailSafely } from "@/lib/email-sender";
import { findProspectById } from "@/lib/institution-data";
import { getWorkflowState, saveWorkflowState } from "@/lib/workflow-state-store";

type RouteContext = {
  params: Promise<{ id: string }>;
};

const subject = "Informasi Rekomendasi Produk Berdasarkan Rencana Pengadaan SiRUP";

function validationError(message: string, status = 400) {
  return NextResponse.json({ ok: false, error: message, mode: getEmailSendMode() }, { status });
}

function unexpectedError(error: unknown) {
  const message = error instanceof Error ? error.message : "Unexpected email send error.";
  return NextResponse.json({ ok: false, error: message, mode: getEmailSendMode() }, { status: 500 });
}

export async function GET() {
  return NextResponse.json({ mode: getEmailSendMode(), subject });
}

export async function POST(request: Request, context: RouteContext) {
  try {
    const { id } = await context.params;
    const body = (await request.json().catch(() => ({}))) as { confirm?: boolean };

    if (body.confirm !== true) {
      return validationError("Send confirmation is required.");
    }

    const institution = findProspectById(id);
    if (!institution) {
      return validationError("Institution not found.", 404);
    }

    const state = getWorkflowState(id);
    const contactEmail = institution.contact_email.trim();
    const draftText = state.draft.text.trim();

    if (!contactEmail) {
      return validationError("Contact email is required before sending.");
    }
    if (!draftText) {
      return validationError("Approved draft text is required before sending.");
    }
    if (!state.draft.approved) {
      return validationError("Draft must be approved before sending.");
    }
    if (!state.draft.readyToSend) {
      return validationError("Draft must be marked Ready to Send before sending.");
    }
    if (state.draft.sent) {
      return validationError("Email has already been sent for this institution.", 409);
    }

    const payload = {
      to: contactEmail,
      subject,
      body: draftText,
      metadata: {
        institutionId: id,
        institutionName: institution.institution_name,
        institutionDisplayName: institution.institution_display_name,
      },
    };
    const result = await sendEmailSafely(payload);
    const sentAt = new Date().toISOString();

    appendEmailSendHistory({
      institutionId: id,
      sentAt,
      mode: result.mode,
      intendedRecipient: result.intendedRecipient,
      actualRecipient: result.actualRecipient,
      subject: result.subject,
      providerMessageId: result.providerMessageId,
      status: result.status,
      error: result.error,
    });

    if (result.status === "failed") {
      const failedState = saveWorkflowState(id, {
        emailSend: {
          sentAt,
          mode: result.mode,
          intendedRecipient: result.intendedRecipient,
          actualRecipient: result.actualRecipient,
          subject: result.subject,
          status: "failed",
          providerMessageId: result.providerMessageId,
          error: result.error,
        },
      });

      return NextResponse.json({ ok: false, error: result.error ?? "Email send failed.", mode: result.mode, state: failedState }, { status: 502 });
    }

    const completedEvents = Array.from(new Set([...state.timeline.completedEvents, "EMAIL_SENT" as const]));
    const nextState = saveWorkflowState(id, {
      draft: {
        text: state.draft.text,
        status: "SENT",
        reviewStatus: "Sent placeholder",
        approved: true,
        readyToSend: true,
        sent: true,
        updatedAt: sentAt,
      },
      timeline: {
        completedEvents,
        eventTimestamps: { ...state.timeline.eventTimestamps, EMAIL_SENT: sentAt },
        currentStage: "Email Sent",
        updatedAt: sentAt,
      },
      emailSend: {
        sentAt,
        mode: result.mode,
        intendedRecipient: result.intendedRecipient,
        actualRecipient: result.actualRecipient,
        subject: result.subject,
        status: "sent",
        providerMessageId: result.providerMessageId,
        error: null,
      },
    });

    return NextResponse.json({ ok: true, mode: result.mode, result, state: nextState });
  } catch (error) {
    return unexpectedError(error);
  }
}
