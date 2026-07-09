"use client";

import { useEffect, useMemo, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { draftStatusLabels } from "@/lib/display-labels";
import type { DraftWorkflowStatus, EmailSendMode, WorkflowState, WorkflowStatePatch } from "@/lib/workflow-state-types";

type DraftGeneratorProps = {
  institutionId: string;
  institutionDisplayName: string;
  contactEmail: string;
  categories: string[];
  packageCount: number;
  totalPagu: number;
  examples: string[];
  monthsFound: string;
};

type TemplateVariables = {
  recipient_name?: string;
  sales_name?: string;
  company_name?: string;
  products?: string;
  product_category?: string;
  need_categories?: string;
  institution_name?: string;
  year?: string;
  evidence_source?: string;
  job_title?: string;
  phone?: string;
  email?: string;
  website?: string;
};

const emailSubject = "Informasi Produk Berdasarkan Rencana Pengadaan SiRUP";

const defaultEmailTemplate = `Yth. {{recipient_name}},

Perkenalkan, saya {{sales_name}} dari {{company_name}}. Kami menyediakan {{products}} untuk mendukung kebutuhan {{product_category}} bagi berbagai institusi dan organisasi.

Kami menghubungi Bapak/Ibu terkait rencana pengadaan {{need_categories}} oleh {{institution_name}} untuk tahun {{year}}, sebagaimana dipublikasikan melalui {{evidence_source}}.

Terkait kebutuhan tersebut, kami dapat menyediakan informasi produk, spesifikasi teknis, katalog, maupun referensi implementasi yang relevan sebagai bahan pertimbangan.

Apabila Bapak/Ibu berkenan, apakah kami dapat mengetahui PIC yang tepat untuk kebutuhan ini, atau menjadwalkan percakapan singkat melalui telepon pada waktu yang sesuai?

Terima kasih atas waktu dan perhatian Bapak/Ibu.

Hormat kami,

{{sales_name}}
{{job_title}}
{{company_name}}
{{phone}} | {{email}} | {{website}}`;

function statusTone(status: DraftWorkflowStatus) {
  if (["READY_TO_SEND", "APPROVED", "SENT"].includes(status)) return "success";
  if (status === "UNDER_REVIEW") return "warning";
  if (status === "NOT_GENERATED") return "neutral";
  return "info";
}

function clean(value: string | undefined | null) {
  return value?.trim() ?? "";
}

function inferYear(monthsFound: string) {
  return monthsFound.match(/20\d{2}/)?.[0] ?? new Date().getFullYear().toString();
}

function substituteTemplate(template: string, variables: Required<TemplateVariables>) {
  let output = template;
  for (const [key, value] of Object.entries(variables)) {
    output = output.replaceAll(`{{${key}}}`, value);
  }
  return output.replace(/\{\{[^}]+\}\}/g, "").replace(/[ \t]+\|[ \t]*$/gm, "").replace(/^[ \t]*\|[ \t]+/gm, "").replace(/^[\s|]+$/gm, "").replace(/[ \t]+\|[ \t]+\|[ \t]+/g, " | ").replace(/\n{3,}/g, "\n\n").trim();
}

function buildDraft(props: DraftGeneratorProps) {
  const categoryText = props.categories.length > 0 ? props.categories.join(", ") : "kebutuhan yang tercatat dalam data perencanaan";
  const products = props.categories.length > 0 ? `produk dan layanan terkait ${categoryText}` : "produk dan layanan yang relevan";
  const variables: Required<TemplateVariables> = {
    recipient_name: "Bapak/Ibu",
    sales_name: "tim sales",
    company_name: "perusahaan kami",
    products,
    product_category: categoryText,
    need_categories: categoryText,
    institution_name: props.institutionDisplayName,
    year: inferYear(props.monthsFound),
    evidence_source: "SiRUP sebagai data perencanaan pengadaan",
    job_title: "",
    phone: "",
    email: clean(props.contactEmail) ? "" : "",
    website: "",
  };

  const draft = substituteTemplate(defaultEmailTemplate, variables);
  return draft.replace(/\nperusahaan kami\n\n$/i, "\nperusahaan kami");
}

function formatLocalTimestamp(value: string | null) {
  if (!value) return "Belum disimpan";
  return new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function sendButtonLabel(mode: EmailSendMode) {
  if (mode === "real") return "Kirim Email";
  if (mode === "test") return "Kirim Email Uji";
  return "Catat Pengiriman Mock";
}

async function postWorkflowState(institutionId: string, patch: WorkflowStatePatch) {
  const response = await fetch(`/api/institutions/${encodeURIComponent(institutionId)}/workflow-state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error("Gagal menyimpan status workflow");
  return (await response.json()) as WorkflowState;
}

type SendEmailPayload = { ok?: boolean; error?: string; state?: WorkflowState; mode?: EmailSendMode };

function parseSendEmailPayload(text: string) {
  if (!text.trim()) return { error: "API pengiriman email mengembalikan respons kosong." };
  try {
    const payload = JSON.parse(text) as SendEmailPayload;
    return { payload };
  } catch {
    return { error: "API pengiriman email mengembalikan JSON yang tidak valid." };
  }
}

export default function DraftGenerator(props: DraftGeneratorProps) {
  const generatedDraft = useMemo(() => buildDraft(props), [props]);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<DraftWorkflowStatus>("NOT_GENERATED");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState("Memuat");
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
        setSaveMessage(state.draft.updatedAt ? "Draf tersimpan dimuat" : "Belum ada draf tersimpan");
        if (state.emailSend.sentAt) setSendMessage(`Terkirim ${formatLocalTimestamp(state.emailSend.sentAt)} ke ${state.emailSend.actualRecipient || props.contactEmail}`);
      })
      .catch(() => {
        if (active) setSaveMessage("Draf tersimpan tidak dapat dimuat");
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
        reviewStatus: draftStatusLabels[nextStatus],
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
    setSaveMessage("Tersimpan ke backend");
    return state;
  }

  function generateDraft() {
    setDraft(generatedDraft);
    setStatus("GENERATED");
    setUpdatedAt(null);
    setSaveMessage("Draf dibuat. Simpan draf agar tersimpan.");
  }

  function updateDraft(value: string) {
    setDraft(value);
    setStatus(value.trim() ? "EDITED" : "NOT_GENERATED");
    setUpdatedAt(null);
    setSendMessage("");
    setSendError(null);
    setSaveMessage(value.trim() ? "Draf diedit. Simpan draf agar tersimpan." : "Draf dikosongkan. Simpan draf agar tersimpan.");
  }

  async function saveDraft() { if (hasDraft) await persistDraft(draft, "SAVED"); }
  async function resetDraft() { await persistDraft("", "NOT_GENERATED"); }
  async function markUnderReview() { if (hasDraft) await persistDraft(draft, "UNDER_REVIEW"); }
  async function approveDraft() { if (hasDraft) await persistDraft(draft, "APPROVED"); }
  async function markReadyToSend() { if (hasDraft && status === "APPROVED") await persistDraft(draft, "READY_TO_SEND"); }

  async function sendEmail() {
    setIsSending(true);
    setSendError(null);
    setSendMessage("Mengirim...");
    try {
      const response = await fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/send-email`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) });
      const text = await response.text();
      const { payload, error } = parseSendEmailPayload(text);
      if (error || !payload) {
        const message = error ?? "Respons API pengiriman email tidak dapat dibaca.";
        setSendError(message);
        setSendMessage(message);
        return;
      }
      if (!response.ok || !payload.ok || !payload.state) {
        const message = payload.error ?? `Pengiriman gagal dengan status ${response.status}.`;
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
      setSendMessage(`Terkirim ${formatLocalTimestamp(payload.state.emailSend.sentAt)} ke ${payload.state.emailSend.actualRecipient || props.contactEmail}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Pengiriman gagal.";
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
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Peninjauan dan Persetujuan Draf</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Draf email outreach berbasis bukti</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Buat, edit, simpan, setujui, pratinjau, dan kirim melalui mode terkontrol. Tidak ada pengiriman otomatis atau massal.</p>
        </div>
        <div className="flex flex-wrap gap-2"><Badge tone={statusTone(status)}>{draftStatusLabels[status]}</Badge>{status === "READY_TO_SEND" ? <Badge tone="success">Siap Dikirim</Badge> : null}{alreadySent ? <Badge tone="success">Terkirim</Badge> : null}</div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[0.75fr_1.25fr]">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Metadata draf</p><dl className="mt-3 space-y-3 text-sm leading-6 text-slate-700"><div><dt className="font-medium text-slate-950">Status workflow</dt><dd className="mt-1">{draftStatusLabels[status]}</dd></div><div><dt className="font-medium text-slate-950">Diperbarui</dt><dd className="mt-1">{formatLocalTimestamp(updatedAt)}</dd></div><div><dt className="font-medium text-slate-950">Penyimpanan</dt><dd className="mt-1">{saveMessage}</dd></div></dl></div>
        <div className="rounded-md border border-slate-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Kontrol workflow</p><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={generateDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Buat Draf</button><button type="button" onClick={saveDraft} disabled={!hasDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Simpan Draf</button><button type="button" onClick={resetDraft} disabled={!hasDraft && status === "NOT_GENERATED"} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Reset Draf</button><button type="button" onClick={markUnderReview} disabled={!hasDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Ajukan Peninjauan</button><button type="button" onClick={approveDraft} disabled={!hasDraft} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Setujui</button><button type="button" onClick={markReadyToSend} disabled={!hasDraft || status !== "APPROVED"} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Siap Dikirim</button></div><p className="mt-3 text-xs leading-5 text-slate-500">Status workflow tersimpan di backend.</p></div>
      </div>

      <label className="mt-5 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Draf Email<textarea value={draft} onChange={(event) => updateDraft(event.target.value)} placeholder="Buat draf untuk mulai mengedit isi outreach." className="mt-2 min-h-80 w-full rounded-md border border-slate-200 bg-white p-4 text-sm font-medium leading-6 text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>

      <Card tone="muted" className="mt-5 p-4 shadow-none">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Pratinjau Email</p><h3 className="mt-2 text-sm font-semibold text-slate-950">Pengiriman terkontrol</h3></div><Badge tone={sendMode === "real" ? "warning" : sendMode === "test" ? "info" : "neutral"}>{sendMode.toUpperCase()}</Badge></div>
        {!props.contactEmail ? <p className="mt-3 text-sm leading-6 text-slate-600">Email kontak belum tersedia.</p> : !hasDraft ? <p className="mt-3 text-sm leading-6 text-slate-600">Draf belum dibuat.</p> : status !== "READY_TO_SEND" && !alreadySent ? <p className="mt-3 text-sm leading-6 text-slate-600">Menunggu persetujuan dan status Siap Dikirim sebelum pratinjau email aktif.</p> : (
          <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700"><p><span className="font-medium text-slate-950">Kepada:</span> {props.contactEmail}</p><p><span className="font-medium text-slate-950">Subjek:</span> {sendMode === "test" ? `[TEST REDIRECT] ${emailSubject}` : emailSubject}</p><pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700">{draft}</pre>{alreadySent ? <p className="text-sm text-slate-600">Terkirim {formatLocalTimestamp(emailSend?.sentAt ?? null)} ke {emailSend?.actualRecipient || props.contactEmail}.</p> : <button type="button" onClick={sendEmail} disabled={!canPreview} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">{isSending ? "Mengirim..." : sendButtonLabel(sendMode)}</button>}<p className={`text-xs leading-5 ${sendError ? "text-red-600" : "text-slate-500"}`}>{sendMessage || "Pratinjau diperlukan sebelum pengiriman. Pengiriman massal tidak tersedia."}</p></div>
        )}
      </Card>
    </Card>
  );
}