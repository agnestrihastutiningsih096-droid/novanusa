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
};

export function getEmailSendMode(): EmailSendMode {
  const mode = (process.env.EMAIL_SEND_MODE ?? "mock").toLowerCase();

  if (mode === "test" || mode === "real" || mode === "mock") {
    return mode;
  }

  return "mock";
}

export async function sendEmailSafely(payload: EmailPayload): Promise<EmailSendResult> {
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
    };
  }

  if (!from || !resendApiKey) {
    return {
      mode,
      intendedRecipient,
      actualRecipient: mode === "test" ? (process.env.EMAIL_TEST_RECIPIENT ?? "") : intendedRecipient,
      subject: payload.subject,
      providerMessageId: null,
      status: "failed",
      error: "EMAIL_FROM and RESEND_API_KEY are required for test/real email modes.",
    };
  }

  const actualRecipient = mode === "test" ? process.env.EMAIL_TEST_RECIPIENT : intendedRecipient;

  if (!actualRecipient) {
    return {
      mode,
      intendedRecipient,
      actualRecipient: "",
      subject: payload.subject,
      providerMessageId: null,
      status: "failed",
      error: "EMAIL_TEST_RECIPIENT is required in test mode.",
    };
  }

  const subject = mode === "test" ? `[TEST REDIRECT] ${payload.subject}` : payload.subject;
  const text = mode === "test" ? `${payload.body}\n\n---\nTEST REDIRECT: Intended recipient was ${intendedRecipient}.` : payload.body;

  try {
    const response = await fetch("https://api.resend.com/emails", {
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
        error: data.message ?? `Email provider returned ${response.status}`,
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
    };
  } catch (error) {
    return {
      mode,
      intendedRecipient,
      actualRecipient,
      subject,
      providerMessageId: null,
      status: "failed",
      error: error instanceof Error ? error.message : "Unknown email send error",
    };
  }
}
