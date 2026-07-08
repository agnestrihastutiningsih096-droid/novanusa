"use client";

import { useEffect, useMemo, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { formatIdr } from "@/lib/institution-utils";
import type { DraftWorkflowStatus, EmailSendMode, WorkflowState, WorkflowStatePatch } from "@/lib/workflow-state-types";

type DraftGeneratorProps = {
  institutionId: string;
  institutionDisplayName: string;
  contactEmail: string;
  categories: string[];
  packageCount: number;
  totalPagu: number;
  examples: string[];
};

const emailSubject = "Informasi Rekomendasi Produk Berdasarkan Rencana Pengadaan SiRUP";

const statusLabels: Record<DraftWorkflowStatus, string> = {
  NOT_GENERATED: "Not Generated",
  GENERATED: "Generated",
  EDITED: "Edited",
  SAVED: "Saved",
  UNDER_REVIEW: "Under Review",
  APPROVED: "Approved",
  READY_TO_SEND: "Ready to Send",
  SENT: "Sent",
};

function statusTone(status: DraftWorkflowStatus) {
  if (["READY_TO_SEND", "APPROVED", "SENT"].includes(status)) return "success";
  if (status === "UNDER_REVIEW") return "warning";
  if (status === "NOT_GENERATED") return "neutral";
  return "info";
}

function buildDraft({ institutionDisplayName, categories, packageCount, totalPagu, examples }: DraftGeneratorProps) {
  const categoryText = categories.length > 0 ? categories.join(", ") : "kategori yang belum terklasifikasi";
  const exampleText = examples.length > 0 ? `\n\nSebagai referensi awal, contoh nama paket yang tercatat antara lain: ${examples.slice(0, 3).join("; ")}.` : "";

  return `Yth. Bapak/Ibu Tim Pengadaan ${institutionDisplayName},

Berdasarkan informasi rencana pengadaan yang dipublikasikan secara resmi melalui SiRUP, kami mencatat adanya indikasi area kebutuhan pada kategori ${categoryText}. Ringkasan awal ini berasal dari ${packageCount.toLocaleString("id-ID")} paket rencana dengan total pagu ${formatIdr(totalPagu)}.${exampleText}

Apabila berkenan, kami dapat menyampaikan referensi produk atau klarifikasi awal yang relevan dengan kategori tersebut untuk membantu proses penelaahan internal Bapak/Ibu.

Catatan: informasi SiRUP merupakan informasi perencanaan pengadaan. Draft ini tidak menyimpulkan status tender, ketersediaan anggaran final, atau keputusan pengadaan.

Hormat kami,
Tim NovaNusa`;
}

function formatLocalTimestamp(value: string | null) {
  if (!value) return "Not saved yet";
  return new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function sendButtonLabel(mode: EmailSendMode) {
  if (mode === "real") return "Send Real Email";
  if (mode === "test") return "Send Test Email";
  return "Record Mock Send";
}

async function postWorkflowState(institutionId: string, patch: WorkflowStatePatch) {
  const response = await fetch(`/api/institutions/${encodeURIComponent(institutionId)}/workflow-state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error("Failed to save workflow state");
  return (await response.json()) as WorkflowState;
}

type SendEmailPayload = {
  ok?: boolean;
  error?: string;
  state?: WorkflowState;
  mode?: EmailSendMode;
};

function parseSendEmailPayload(text: string) {
  if (!text.trim()) {
    return { error: "Email send API returned an empty response." };
  }

  try {
    const payload = JSON.parse(text) as SendEmailPayload;
    return { payload };
  } catch {
    return { error: "Email send API returned invalid JSON." };
  }
}

export default function DraftGenerator(props: DraftGeneratorProps) {
  const generatedDraft = useMemo(() => buildDraft(props), [props]);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<DraftWorkflowStatus>("NOT_GENERATED");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState("Load pending");
  const [sendMode, setSendMode] = useState<EmailSendMode>("mock");
  const [emailSend, setEmailSend] = useState<WorkflowState["emailSend"] | null>(null);
  const [sendMessage, setSendMessage] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const hasDraft = draft.trim().length > 0;
  const alreadySent = status === "SENT" || Boolean(emailSend?.sentAt && emailSend.status === "sent");
  const canPreview = hasDraft && status === "READY_TO_SEND" && Boolean(props.contactEmail) && !alreadySent && !isSending;

  useEffect(() => {
    let active = true;

    Promise.all([
      fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/workflow-state`).then((response) => response.json() as Promise<WorkflowState>),
      fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/send-email`).then((response) => response.json() as Promise<{ mode: EmailSendMode }>),
    ])
      .then(([state, sendConfig]) => {
        if (!active) return;
        setDraft(state.draft.text);
        setStatus(state.draft.status);
        setUpdatedAt(state.draft.updatedAt);
        setEmailSend(state.emailSend);
        setSendMode(sendConfig.mode ?? "mock");
        setSaveMessage(state.draft.updatedAt ? "Loaded saved draft" : "No saved draft yet");
        if (state.emailSend.sentAt) setSendMessage(`Sent ${formatLocalTimestamp(state.emailSend.sentAt)} to ${state.emailSend.actualRecipient || props.contactEmail}`);
      })
      .catch(() => {
        if (active) setSaveMessage("Could not load saved draft");
      });

    return () => {
      active = false;
    };
  }, [props.contactEmail, props.institutionId]);

  async function persistDraft(nextDraft: string, nextStatus: DraftWorkflowStatus) {
    const now = new Date().toISOString();
    const state = await postWorkflowState(props.institutionId, {
      draft: {
        text: nextDraft,
        status: nextStatus,
        reviewStatus: statusLabels[nextStatus],
        approved: nextStatus === "APPROVED" || nextStatus === "READY_TO_SEND" || nextStatus === "SENT",
        readyToSend: nextStatus === "READY_TO_SEND" || nextStatus === "SENT",
        sent: nextStatus === "SENT",
        updatedAt: now,
      },
    });
    setDraft(state.draft.text);
    setStatus(state.draft.status);
    setUpdatedAt(state.draft.updatedAt);
    setEmailSend(state.emailSend);
    setSaveMessage("Saved to backend");
    return state;
  }

  function generateDraft() {
    setDraft(generatedDraft);
    setStatus("GENERATED");
    setUpdatedAt(null);
    setSaveMessage("Generated. Save draft to persist.");
  }

  function updateDraft(value: string) {
    setDraft(value);
    setStatus(value.trim() ? "EDITED" : "NOT_GENERATED");
    setUpdatedAt(null);
    setSendMessage("");
    setSendError(null);
    setSaveMessage(value.trim() ? "Edited. Save draft to persist." : "Draft cleared. Save draft to persist.");
  }

  async function saveDraft() { if (hasDraft) await persistDraft(draft, "SAVED"); }
  async function resetDraft() { await persistDraft("", "NOT_GENERATED"); }
  async function markUnderReview() { if (hasDraft) await persistDraft(draft, "UNDER_REVIEW"); }
  async function approveDraft() { if (hasDraft) await persistDraft(draft, "APPROVED"); }
  async function markReadyToSend() { if (hasDraft && status === "APPROVED") await persistDraft(draft, "READY_TO_SEND"); }

  async function sendEmail() {
    setIsSending(true);
    setSendError(null);
    setSendMessage("Sending...");

    try {
      const response = await fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/send-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      });
      const text = await response.text();
      const { payload, error } = parseSendEmailPayload(text);

      if (error || !payload) {
        const message = error ?? "Email send API returned an unreadable response.";
        setSendError(message);
        setSendMessage(message);
        return;
      }

      if (!response.ok || !payload.ok || !payload.state) {
        const message = payload.error ?? `Send failed with status ${response.status}.`;
        setSendError(message);
        setSendMessage(message);
        if (payload.state?.emailSend) setEmailSend(payload.state.emailSend);
        return;
      }

      setDraft(payload.state.draft.text);
      setStatus(payload.state.draft.status);
      setUpdatedAt(payload.state.draft.updatedAt);
      setEmailSend(payload.state.emailSend);
      setSendMode(payload.mode ?? sendMode);
      setSendMessage(`Sent ${formatLocalTimestamp(payload.state.emailSend.sentAt)} to ${payload.state.emailSend.actualRecipient || props.contactEmail}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Send failed.";
      setSendError(message);
      setSendMessage(message);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <Card className="p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Draft Review & Approval</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Evidence-based cold outreach draft</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Generate, edit, save, approve, preview, and send through a safe controlled mode. No automatic or bulk sending.</p>
        </div>
        <div className="flex flex-wrap gap-2"><Badge tone={statusTone(status)}>{statusLabels[status]}</Badge>{status === "READY_TO_SEND" ? <Badge tone="success">Ready to Send</Badge> : null}{alreadySent ? <Badge tone="success">Sent</Badge> : null}</div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[0.75fr_1.25fr]">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Draft metadata</p><dl className="mt-3 space-y-3 text-sm leading-6 text-slate-700"><div><dt className="font-medium text-slate-950">Workflow state</dt><dd className="mt-1">{statusLabels[status]}</dd></div><div><dt className="font-medium text-slate-950">Updated</dt><dd className="mt-1">{formatLocalTimestamp(updatedAt)}</dd></div><div><dt className="font-medium text-slate-950">Persistence</dt><dd className="mt-1">{saveMessage}</dd></div></dl></div>
        <div className="rounded-md border border-slate-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Workflow controls</p><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={generateDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Generate Draft</button><button type="button" onClick={saveDraft} disabled={!hasDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Save Draft</button><button type="button" onClick={resetDraft} disabled={!hasDraft && status === "NOT_GENERATED"} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Reset Draft</button><button type="button" onClick={markUnderReview} disabled={!hasDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Mark as Under Review</button><button type="button" onClick={approveDraft} disabled={!hasDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Approve Draft</button><button type="button" onClick={markReadyToSend} disabled={!hasDraft || status !== "APPROVED"} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Mark Ready to Send</button></div><p className="mt-3 text-xs leading-5 text-slate-500">Backend-persisted workflow state.</p></div>
      </div>

      <label className="mt-5 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Editable draft<textarea value={draft} onChange={(event) => updateDraft(event.target.value)} placeholder="Generate a draft to edit the outreach text." className="mt-2 min-h-80 w-full rounded-md border border-slate-200 bg-white p-4 text-sm font-medium leading-6 text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>

      <Card tone="muted" className="mt-5 p-4 shadow-none">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Email Preview</p><h3 className="mt-2 text-sm font-semibold text-slate-950">Controlled send</h3></div><Badge tone={sendMode === "real" ? "warning" : sendMode === "test" ? "info" : "neutral"}>{sendMode.toUpperCase()}</Badge></div>
        {!props.contactEmail ? <p className="mt-3 text-sm leading-6 text-slate-600">No contact email yet.</p> : !hasDraft ? <p className="mt-3 text-sm leading-6 text-slate-600">Draft not generated.</p> : status !== "READY_TO_SEND" && !alreadySent ? <p className="mt-3 text-sm leading-6 text-slate-600">Waiting approval and Ready to Send status before email preview is active.</p> : (
          <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700"><p><span className="font-medium text-slate-950">To:</span> {props.contactEmail}</p><p><span className="font-medium text-slate-950">Subject:</span> {sendMode === "test" ? `[TEST REDIRECT] ${emailSubject}` : emailSubject}</p><pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700">{draft}</pre>{alreadySent ? <p className="text-sm text-slate-600">Sent {formatLocalTimestamp(emailSend?.sentAt ?? null)} to {emailSend?.actualRecipient || props.contactEmail}.</p> : <button type="button" onClick={sendEmail} disabled={!canPreview} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">{isSending ? "Sending..." : sendButtonLabel(sendMode)}</button>}<p className={`text-xs leading-5 ${sendError ? "text-red-600" : "text-slate-500"}`}>{sendMessage || "Preview required before sending. No bulk sending is available."}</p></div>
        )}
      </Card>
    </Card>
  );
}
