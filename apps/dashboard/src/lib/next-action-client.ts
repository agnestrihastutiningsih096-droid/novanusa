import { operatorHeaders } from "./operator-auth";
import type { NextActionCommandRequest, NextActionCommandResponse } from "./next-action-contract.ts";

type FetchLike = typeof fetch;

export function sendNextActionCommandIfActive(
  institutionId: string,
  operatorToken: string,
  operatorReady: boolean,
  command: NextActionCommandRequest,
  fetchImpl: FetchLike = fetch,
) {
  if (!operatorReady || !operatorToken) return null;
  return fetchImpl(`/api/institutions/${encodeURIComponent(institutionId)}/next-action`, {
    method: "POST",
    headers: operatorHeaders(operatorToken),
    body: JSON.stringify(command),
  }) as Promise<Response & { json(): Promise<NextActionCommandResponse> }>;
}
