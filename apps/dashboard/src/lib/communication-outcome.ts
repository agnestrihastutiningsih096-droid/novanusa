export const COMMUNICATION_OUTCOMES = [
  "interested",
  "no_decision",
  "not_interested",
  "no_response",
  "invalid_contact",
] as const;

export type CommunicationOutcome = (typeof COMMUNICATION_OUTCOMES)[number];

export type CommunicationOutcomeRecord = {
  id: string;
  institutionId: string;
  procurementIdentityId: string | null;
  outcome: CommunicationOutcome;
  note: string | null;
  actor: string;
  recordedAt: string;
};

export type CommunicationOutcomeResult = {
  data: CommunicationOutcomeRecord;
  audit: { eventId: string };
};

export type CommunicationOutcomeAppend = {
  commandId: string;
  canonicalContent: string;
  record: CommunicationOutcomeRecord;
  audit: {
    eventId: string;
    commandId: string;
    actor: string;
    recordedAt: string;
    action: "communication_outcome.recorded";
    institutionId: string;
    procurementIdentityId: string | null;
    outcomeId: string;
  };
};

export type CommunicationOutcomeAppendResult =
  | { status: "created"; result: CommunicationOutcomeResult }
  | { status: "replayed"; result: CommunicationOutcomeResult }
  | { status: "conflict" };

export type CommunicationOutcomePriorCommand = {
  canonicalContent: string;
  result: CommunicationOutcomeResult;
};
