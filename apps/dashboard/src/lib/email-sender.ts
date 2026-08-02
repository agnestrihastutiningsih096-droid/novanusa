import type { EmailSendMode } from "@/lib/workflow-state-types";

export type EmailPayload = {
  to: string;
  subject: string;
  body: string;
  metadata: Record<string, string>;
};

export type EmailSendResult = {
  mode: EmailSendMode;
  intendedRecipient: string;
  actualRecipient: string;
  subject: string;
  providerMessageId: string | null;
  status: "sent" | "failed";
  error: string | null;
  errorCode: string | null;
};

type FetchLike = typeof fetch;

export function getOperatorActor(request: Request): string | null {
  const expected = process.env.NOVANUSA_OPERATOR_TOKEN;
  const supplied = request.headers.get("x-novanusa-operator-token");
  if (!expected || !supplied || expected.length < 16 || supplied !== expected) return null;
  return "local-operator";
}

export function getTestRecipient(): { recipient: string; errorCode: string | null } {
  const recipient = (process.env.EMAIL_TEST_RECIPIENT ?? "").trim().toLowerCase();
  const allowlist = new Set(
    (process.env.EMAIL_TEST_RECIPIENT_ALLOWLIST ?? "")
      .split(/[\s,;]+/)
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  );
  if (!recipient) return { recipient: "", errorCode: "TEST_RECIPIENT_MISSING" };
  if (!allowlist.has(recipient)) return { recipient, errorCode: "TEST_RECIPIENT_NOT_ALLOWLISTED" };
  return { recipient, errorCode: null };
}

export function getEmailSendMode(): EmailSendMode {
  const mode = (process.env.EMAIL_SEND_MODE ?? "mock").toLowerCase();

  if (mode === "test" || mode === "real" || mode === "mock") {
    return mode;
  }

  return "mock";
}

export async function sendEmailSafely(payload: EmailPayload, fetchImpl: FetchLike = fetch): Promise<EmailSendResult> {
  const mode = getEmailSendMode();
  const intendedRecipient = payload.to;
  const from = process.env.EMAIL_FROM;
  const resendApiKey = process.env.RESEND_API_KEY;

  if (mode === "mock") {
    return {
      mode,
      intendedRecipient,
      actualRecipient: "mock:no-real-recipient",
      subject: payload.subject,
      providerMessageId: `mock-${Date.now()}`,
      status: "sent",
      error: null,
      errorCode: null,
    };
  }

  if (mode === "real") {
    return {
      mode, intendedRecipient, actualRecipient: "", subject: payload.subject, providerMessageId: null,
      status: "failed", error: "Real email mode is temporarily disabled.", errorCode: "REAL_MODE_DISABLED",
    };
  }

  const testRecipient = getTestRecipient();
  const actualRecipient = testRecipient.recipient;
  const subject = `[TEST REDIRECT] ${payload.subject}`;
  if (testRecipient.errorCode) {
    return {
      mode, intendedRecipient, actualRecipient, subject, providerMessageId: null,
      status: "failed", error: "Test recipient configuration is not permitted.", errorCode: testRecipient.errorCode,
    };
  }

  if (!from || !resendApiKey) {
    return {
      mode,
      intendedRecipient,
      actualRecipient,
      subject,
      providerMessageId: null,
      status: "failed",
      error: "Email provider credentials are not configured.",
      errorCode: "PROVIDER_CREDENTIALS_MISSING",
    };
  }

  const text = `${payload.body}\n\n---\nTEST REDIRECT: Intended recipient was ${intendedRecipient}.`;

  try {
    const response = await fetchImpl("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${resendApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from,
        to: actualRecipient,
        subject,
        text,
        headers: {
          "X-NovaNusa-Mode": mode,
          "X-NovaNusa-Intended-Recipient": intendedRecipient,
        },
      }),
    });

    const data = (await response.json().catch(() => ({}))) as { id?: string; message?: string };

    if (!response.ok) {
      return {
        mode,
        intendedRecipient,
        actualRecipient,
        subject,
        providerMessageId: null,
        status: "failed",
        error: `Email provider rejected the request (${response.status}).`,
        errorCode: "PROVIDER_REJECTED",
      };
    }

    return {
      mode,
      intendedRecipient,
      actualRecipient,
      subject,
      providerMessageId: data.id ?? null,
      status: "sent",
      error: null,
      errorCode: null,
    };
  } catch {
    return {
      mode,
      intendedRecipient,
      actualRecipient,
      subject,
      providerMessageId: null,
      status: "failed",
      error: "Email provider could not be reached.",
      errorCode: "PROVIDER_UNAVAILABLE",
    };
  }
}
