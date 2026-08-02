import { operatorHeaders } from "./operator-auth";
import type { SalesNotesCommandRequest, SalesNotesCommandResponse } from "./sales-notes-contract.ts";

type FetchLike = typeof fetch;

export function sendSalesNotesCommandIfActive(
  institutionId: string,
  operatorToken: string,
  operatorReady: boolean,
  command: SalesNotesCommandRequest,
  fetchImpl: FetchLike = fetch,
) {
  if (!operatorReady || !operatorToken) return null;
  return fetchImpl(`/api/institutions/${encodeURIComponent(institutionId)}/sales-notes`, {
    method: "POST",
    headers: operatorHeaders(operatorToken),
    body: JSON.stringify(command),
  }) as Promise<Response & { json(): Promise<SalesNotesCommandResponse> }>;
}
