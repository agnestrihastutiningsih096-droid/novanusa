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
  };
  salesNotes: {
    contactPerson: string;
    conversationNotes: string;
    customerInterest: string;
    requestedDocuments: string;
    internalNotes: string;
    savedAt: string | null;
  };
  nextAction: {
    action: string;
    note: string;
    savedAt: string | null;
  };
  timeline: {
    completedEvents: TimelineEventKey[];
    eventTimestamps: Partial<Record<TimelineEventKey, string>>;
    currentStage: string;
    updatedAt: string | null;
  };
  emailSend: {
    sentAt: string | null;
    mode: EmailSendMode | null;
    intendedRecipient: string;
    actualRecipient: string;
    subject: string;
    status: "not_sent" | "sent" | "failed";
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
    },
    salesNotes: {
      contactPerson: "",
      conversationNotes: "",
      customerInterest: "",
      requestedDocuments: "",
      internalNotes: "",
      savedAt: null,
    },
    nextAction: {
      action: "Call Again",
      note: "",
      savedAt: null,
    },
    timeline: {
      completedEvents: [],
      eventTimestamps: {},
      currentStage: "No CRM event yet",
      updatedAt: null,
    },
    emailSend: {
      sentAt: null,
      mode: null,
      intendedRecipient: "",
      actualRecipient: "",
      subject: "",
      status: "not_sent",
      providerMessageId: null,
      error: null,
    },
  };
}
