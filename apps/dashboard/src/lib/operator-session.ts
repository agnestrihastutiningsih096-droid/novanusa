export const OPERATOR_TOKEN_SESSION_KEY = "novanusa.operatorToken";

function browserSessionStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.sessionStorage;
}

export function restoreOperatorToken(storage: Storage | null = browserSessionStorage()) {
  return storage?.getItem(OPERATOR_TOKEN_SESSION_KEY)?.trim() ?? "";
}

export function persistOperatorToken(token: string, storage: Storage | null = browserSessionStorage()) {
  storage?.setItem(OPERATOR_TOKEN_SESSION_KEY, token);
}

export function removeOperatorToken(storage: Storage | null = browserSessionStorage()) {
  storage?.removeItem(OPERATOR_TOKEN_SESSION_KEY);
}
