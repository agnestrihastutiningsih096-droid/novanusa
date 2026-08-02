import type { TimelineEventKey } from "@/lib/crm-timeline";

export type DraftWorkflowStatus = "NOT_GENERATED" | "GENERATED" | "EDITED" | "SAVED" | "UNDER_REVIEW" | "APPROVED" | "READY_TO_SEND" | "SENT";

export type EmailSendMode = "mock" | "test" | "real";

export type WorkflowState = {
  draft: {
    text: string;
    status: DraftWorkflowStatus;
    reviewStatus: string;
    approved: boolean;
    readyToSend: boolean;
    sent: boolean;
    updatedAt: string | null;
    version: number;
    approvedBy: string | null;
    approvedAt: string | null;
  };
  salesNotes: {
    contactPerson: string;
    conversationNotes: string;
    customerInterest: string;
    requestedDocuments: string;
    internalNotes: string;
    savedAt: string | null;
    updatedAt: string | null;
    updatedBy: string | null;
  };
  nextAction: {
    action: string;
    note: string;
    savedAt: string | null;
    updatedAt: string | null;
    updatedBy: string | null;
  };
  timeline: {
    completedEvents: TimelineEventKey[];
    eventTimestamps: Partial<Record<TimelineEventKey, string>>;
    currentStage: string;
    updatedAt: string | null;
    updatedBy: string | null;
  };
  emailSend: {
    sentAt: string | null;
    mode: EmailSendMode | null;
    intendedRecipient: string;
    actualRecipient: string;
    subject: string;
    status: "not_sent" | "reserved" | "sent" | "failed";
    idempotencyKey: string | null;
    providerMessageId: string | null;
    error: string | null;
  };
};

export type WorkflowStatePatch = Partial<{
  draft: Partial<WorkflowState["draft"]>;
  salesNotes: Partial<WorkflowState["salesNotes"]>;
  nextAction: Partial<WorkflowState["nextAction"]>;
  timeline: Partial<WorkflowState["timeline"]>;
  emailSend: Partial<WorkflowState["emailSend"]>;
}>;

export type DraftTransitionResult =
  | { ok: true; draft: WorkflowState["draft"] }
  | { ok: false; code: string };

export function applyDraftTransition(
  current: WorkflowState["draft"],
  requested: Partial<WorkflowState["draft"]>,
  actor: string,
  now: string,
): DraftTransitionResult {
  const requestedStatus = requested.status;
  if (requestedStatus === "SENT" || requested.sent === true) {
    return { ok: false, code: "FINAL_STATE_SERVER_ONLY" };
  }

  const text = requested.text ?? current.text;
  const textChanged = text !== current.text;
  if (requestedStatus === "APPROVED") {
    if (!text.trim()) return { ok: false, code: "DRAFT_REQUIRED" };
    return {
      ok: true,
      draft: {
        ...current, text, status: "APPROVED", reviewStatus: "Approved", approved: true, readyToSend: false, sent: false,
        approvedBy: actor, approvedAt: now, updatedAt: now, version: current.version + (textChanged ? 1 : 0),
      },
    };
  }

  if (requestedStatus === "READY_TO_SEND") {
    if (!current.approved || !current.approvedBy || !current.approvedAt || textChanged) {
      return { ok: false, code: "APPROVAL_REQUIRED" };
    }
    return {
      ok: true,
      draft: { ...current, status: "READY_TO_SEND", reviewStatus: "Ready to Send", readyToSend: true, updatedAt: now },
    };
  }

  const safeStatus = requestedStatus ?? (textChanged ? "EDITED" : current.status);
  return {
    ok: true,
    draft: {
      ...current,
      text,
      status: safeStatus,
      reviewStatus: requested.reviewStatus ?? safeStatus,
      approved: textChanged ? false : current.approved,
      readyToSend: textChanged ? false : current.readyToSend,
      sent: false,
      approvedBy: textChanged ? null : current.approvedBy,
      approvedAt: textChanged ? null : current.approvedAt,
      updatedAt: now,
      version: current.version + (textChanged ? 1 : 0),
    },
  };
}

export function createDefaultWorkflowState(): WorkflowState {
  return {
    draft: {
      text: "",
      status: "NOT_GENERATED",
      reviewStatus: "Not Generated",
      approved: false,
      readyToSend: false,
      sent: false,
      updatedAt: null,
      version: 0,
      approvedBy: null,
      approvedAt: null,
    },
    salesNotes: {
      contactPerson: "",
      conversationNotes: "",
      customerInterest: "",
      requestedDocuments: "",
      internalNotes: "",
      savedAt: null,
      updatedAt: null,
      updatedBy: null,
    },
    nextAction: {
      action: "Call Again",
      note: "",
      savedAt: null,
      updatedAt: null,
      updatedBy: null,
    },
    timeline: {
      completedEvents: [],
      eventTimestamps: {},
      currentStage: "No CRM event yet",
      updatedAt: null,
      updatedBy: null,
    },
    emailSend: {
      sentAt: null,
      mode: null,
      intendedRecipient: "",
      actualRecipient: "",
      subject: "",
      status: "not_sent",
      idempotencyKey: null,
      providerMessageId: null,
      error: null,
    },
  };
}
