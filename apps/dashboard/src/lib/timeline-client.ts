import { operatorHeaders } from "./operator-auth";
import type { TimelineCommandRequest, TimelineCommandResponse } from "./timeline-contract.ts";

type FetchLike = typeof fetch;

export function sendTimelineCommandIfActive(
  institutionId: string,
  operatorToken: string,
  operatorReady: boolean,
  command: TimelineCommandRequest,
  fetchImpl: FetchLike = fetch,
) {
  if (!operatorReady || !operatorToken) return null;
  return fetchImpl(`/api/institutions/${encodeURIComponent(institutionId)}/timeline`, {
    method: "POST",
    headers: operatorHeaders(operatorToken),
    body: JSON.stringify(command),
  }) as Promise<Response & { json(): Promise<TimelineCommandResponse> }>;
}
