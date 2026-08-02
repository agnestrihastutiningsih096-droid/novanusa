import type { WorkflowState } from "./workflow-state-types.ts";

export type SalesNotesValues = Pick<
  WorkflowState["salesNotes"],
  "contactPerson" | "conversationNotes" | "customerInterest" | "requestedDocuments" | "internalNotes"
>;

export type SalesNotesCommandRequest =
  | { operation: "update"; notes: SalesNotesValues }
  | { operation: "clear" };

export type SalesNotesCommandResponse =
  | { ok: true; salesNotes: WorkflowState["salesNotes"] }
  | { ok: false; error: { code: string; message: string } };
