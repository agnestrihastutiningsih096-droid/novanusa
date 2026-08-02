type FetchLike = typeof fetch;

export function operatorHeaders(operatorToken: string, headers?: HeadersInit) {
  const result = new Headers(headers);
  result.set("Content-Type", "application/json");
  result.set("x-novanusa-operator-token", operatorToken);
  return result;
}

export function fetchWorkflowStateIfActive(
  institutionId: string,
  operatorToken: string,
  operatorReady: boolean,
  init?: RequestInit,
  fetchImpl: FetchLike = fetch,
) {
  if (!operatorReady || !operatorToken) return null;

  return fetchImpl(`/api/institutions/${encodeURIComponent(institutionId)}/workflow-state`, {
    ...init,
    headers: operatorHeaders(operatorToken, init?.headers),
  });
}
