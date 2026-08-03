import { operatorHeaders } from "./operator-auth.ts";
import type { CommunicationOutcome, CommunicationOutcomeReadResult, CommunicationOutcomeResult } from "./communication-outcome.ts";

type FetchLike = typeof fetch;

export function fetchLatestGenericCommunicationOutcomeIfActive(
  institutionId: string,
  operatorToken: string,
  operatorReady: boolean,
  fetchImpl: FetchLike = fetch,
) {
  if (!operatorReady || !operatorToken) return null;
  return fetchImpl(`/api/institutions/${encodeURIComponent(institutionId)}/communication-outcomes`, {
    headers: operatorHeaders(operatorToken),
  }) as Promise<Response & { json(): Promise<CommunicationOutcomeReadResult> }>;
}

export function sendGenericCommunicationOutcomeIfActive(
  institutionId: string,
  operatorToken: string,
  operatorReady: boolean,
  outcome: CommunicationOutcome,
  note: string,
  fetchImpl: FetchLike = fetch,
  createCommandId: () => string = () => crypto.randomUUID(),
) {
  if (!operatorReady || !operatorToken) return null;
  const trimmedNote = note.trim();
  const command = {
    commandId: createCommandId(),
    outcome,
    ...(trimmedNote ? { note: trimmedNote } : {}),
  };

  return fetchImpl(`/api/institutions/${encodeURIComponent(institutionId)}/communication-outcomes`, {
    method: "POST",
    headers: operatorHeaders(operatorToken),
    body: JSON.stringify(command),
  }) as Promise<Response & { json(): Promise<CommunicationOutcomeResult> }>;
}
