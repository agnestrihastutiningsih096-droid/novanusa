import type { WorkflowState } from "./workflow-state-types.ts";

export const NEXT_ACTION_VALUES = [
  "Call Again",
  "Send Catalog",
  "Send Quotation",
  "Waiting Response",
  "Schedule Meeting",
  "Other",
] as const;

export type NextActionValue = (typeof NEXT_ACTION_VALUES)[number];

export type NextActionValues = {
  action: NextActionValue;
  note: string;
};

export type NextActionCommandRequest =
  | { operation: "update"; nextAction: NextActionValues }
  | { operation: "clear" };

export type NextActionCommandResponse =
  | { ok: true; nextAction: WorkflowState["nextAction"] }
  | { ok: false; error: { code: string; message: string } };
