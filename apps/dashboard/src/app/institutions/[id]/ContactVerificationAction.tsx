"use client";

import { useState } from "react";
import { operatorHeaders } from "@/lib/operator-auth";
import type { ContactVerificationRecord } from "@/lib/contact-verification";
import type { ContactOverrideEvent } from "@/lib/contact-override";
import { useInstitutionOperator } from "./InstitutionOperatorContext";

type Props = {
  institutionId: string;
  contactEmail: string;
  evidenceUrl: string;
  expectedContactFingerprint: string | null;
  verificationSource: "OFFICIAL_INSTITUTION_WEBSITE";
  initialVerification: ContactVerificationRecord | null;
  initialEvents: ContactOverrideEvent[];
};

export default function ContactVerificationAction(props: Props) {
  const { operatorToken, operatorReady } = useInstitutionOperator();
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [verification, setVerification] = useState<ContactVerificationRecord | null>(props.initialVerification);
  const [events, setEvents] = useState(props.initialEvents);
  const [fingerprint, setFingerprint] = useState(props.expectedContactFingerprint);
  const [email, setEmail] = useState(props.contactEmail);
  const [evidenceUrl, setEvidenceUrl] = useState(props.evidenceUrl);
  const [showMismatch, setShowMismatch] = useState(false);
  const [reasonCode, setReasonCode] = useState("NOT_FOUND_ON_OFFICIAL_SOURCE");
  const [reasonDetail, setReasonDetail] = useState("");
  const [mismatchEvidence, setMismatchEvidence] = useState("");
  const [observedEmail, setObservedEmail] = useState("");
  const [replacementEmail, setReplacementEmail] = useState("");
  const [confirmEmail, setConfirmEmail] = useState("");
  const [replacementEvidence, setReplacementEvidence] = useState("");

  async function verifyContact() {
    if (!operatorReady || !fingerprint || !confirmed) return;
    setSubmitting(true);
    setMessage("Memverifikasi...");
    try {
      const response = await fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/contact-verification`, {
        method: "POST",
        headers: operatorHeaders(operatorToken),
        body: JSON.stringify({
          confirm: true,
          expectedContactFingerprint: fingerprint,
          verificationSource: props.verificationSource,
        }),
      });
      const payload = await response.json() as { ok?: boolean; verification?: ContactVerificationRecord; idempotent?: boolean; error?: { code?: string; message?: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.code ?? payload.error?.message ?? "CONTACT_VERIFICATION_FAILED");
      if (!payload.verification) throw new Error("CONTACT_VERIFICATION_RESPONSE_INVALID");
      setVerification(payload.verification);
      setMessage(payload.idempotent ? "Kontak sudah terverifikasi dengan bukti yang sama." : "Kontak berhasil diverifikasi.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "CONTACT_VERIFICATION_FAILED");
    } finally {
      setSubmitting(false);
    }
  }

  async function recordMismatch() {
    if (!fingerprint) return;
    setSubmitting(true); setMessage("Menyimpan ketidakcocokan...");
    try {
      const response = await fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/contact-mismatch`, { method: "POST", headers: operatorHeaders(operatorToken), body: JSON.stringify({ expectedContactFingerprint: fingerprint, reasonCode, evidenceUrl: mismatchEvidence, ...(reasonDetail.trim() ? { reasonDetail } : {}), ...(observedEmail.trim() ? { observedEmail } : {}) }) });
      const payload = await response.json(); if (!response.ok || !payload.ok) throw new Error(payload.error?.code ?? "CONTACT_MISMATCH_FAILED");
      setEvents((current) => [...current, payload.mismatch]); setVerification(null); setFingerprint(null); setEmail(""); setEvidenceUrl(""); setShowMismatch(false); setMessage("Kontak ditandai tidak cocok. Tambahkan pengganti.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "CONTACT_MISMATCH_FAILED"); } finally { setSubmitting(false); }
  }

  async function saveReplacement() {
    const mismatch = [...events].reverse().find((event) => event.type === "MISMATCH" && !events.some((candidate) => candidate.type === "REPLACEMENT" && candidate.parentMismatchId === event.mismatchId));
    if (!mismatch || mismatch.type !== "MISMATCH") return;
    setSubmitting(true); setMessage("Menyimpan pengganti...");
    try {
      const response = await fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/contact-replacement`, { method: "POST", headers: operatorHeaders(operatorToken), body: JSON.stringify({ parentMismatchId: mismatch.mismatchId, email: replacementEmail, confirmEmail, evidenceUrl: replacementEvidence }) });
      const payload = await response.json(); if (!response.ok || !payload.ok) throw new Error(payload.error?.code ?? "CONTACT_REPLACEMENT_FAILED");
      setEvents((current) => [...current, payload.replacement]); setEmail(payload.replacement.email); setEvidenceUrl(payload.replacement.evidenceUrl); setFingerprint(payload.replacement.fingerprint); setVerification(null); setConfirmed(false); setReplacementEmail(""); setConfirmEmail(""); setReplacementEvidence(""); setMessage("Pengganti tersimpan sebagai UNVERIFIED. Lakukan verifikasi manusia.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "CONTACT_REPLACEMENT_FAILED"); } finally { setSubmitting(false); }
  }

  const validContact = Boolean(email && evidenceUrl && fingerprint);

  const openMismatch = [...events].reverse().find((event) => event.type === "MISMATCH" && !events.some((candidate) => candidate.type === "REPLACEMENT" && candidate.parentMismatchId === event.mismatchId));
  return (
    <div className={`mt-5 rounded-md border p-4 ${verification ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}>
      {verification ? <>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">VERIFIED</p>
        <dl className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          <div><dt className="font-medium text-slate-950">Diverifikasi pada</dt><dd>{new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(verification.verifiedAt))}</dd></div>
          <div><dt className="font-medium text-slate-950">Diverifikasi oleh</dt><dd>{verification.verifiedBy}</dd></div>
          <div><dt className="font-medium text-slate-950">Sumber verifikasi</dt><dd>{verification.verificationSource}</dd></div>
        </dl>
      </> : <>
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Verifikasi Kontak</p>
      <dl className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
        <div><dt className="font-medium text-slate-950">Email kontak efektif</dt><dd className="break-all">{email || "Menunggu pengganti"}</dd></div>
        <div><dt className="font-medium text-slate-950">URL bukti</dt><dd className="break-all">{evidenceUrl || "Tidak tersedia"}</dd></div>
        <div><dt className="font-medium text-slate-950">Sumber verifikasi</dt><dd>{props.verificationSource}</dd></div>
      </dl>
      <label className="mt-3 flex items-start gap-2 text-sm leading-5 text-slate-700">
        <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" />
        <span>Saya mengonfirmasi bahwa email di atas tercantum pada URL bukti institusi resmi tersebut.</span>
      </label>
      <button type="button" onClick={verifyContact} disabled={!operatorReady || !confirmed || !validContact || submitting} className="mt-3 h-9 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50">
        {submitting ? "Memverifikasi..." : "Verifikasi Kontak"}
      </button>
      <p className="mt-2 text-xs leading-5 text-slate-500">{message || (!operatorReady ? "Aktifkan operator pada kontrol draf untuk memverifikasi." : "Verifikasi berlaku hanya untuk email dan URL bukti yang ditampilkan.")}</p>
      </>}
      {validContact ? <button type="button" onClick={() => setShowMismatch((value) => !value)} disabled={!operatorReady || submitting} className="mt-3 h-9 rounded-md border border-amber-300 bg-white px-3 text-sm font-medium text-amber-800">Tandai Tidak Cocok</button> : null}
      {showMismatch ? <div className="mt-3 grid gap-2 border-t border-slate-200 pt-3">
        <select value={reasonCode} onChange={(event) => setReasonCode(event.target.value)} className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"><option value="NOT_FOUND_ON_OFFICIAL_SOURCE">Tidak ditemukan di sumber resmi</option><option value="EMAIL_DIFFERS_FROM_OFFICIAL_SOURCE">Email berbeda</option><option value="CONTACT_OBSOLETE">Kontak usang</option><option value="OTHER">Lainnya</option></select>
        <input value={mismatchEvidence} onChange={(event) => setMismatchEvidence(event.target.value)} placeholder="https:// URL bukti resmi yang diperiksa" className="h-9 rounded-md border border-slate-300 px-2 text-sm" />
        <input value={observedEmail} onChange={(event) => setObservedEmail(event.target.value)} placeholder="Email teramati (opsional)" className="h-9 rounded-md border border-slate-300 px-2 text-sm" />
        <textarea value={reasonDetail} onChange={(event) => setReasonDetail(event.target.value)} placeholder="Detail alasan (opsional)" className="rounded-md border border-slate-300 p-2 text-sm" />
        <button type="button" onClick={recordMismatch} disabled={submitting || !mismatchEvidence} className="h-9 rounded-md bg-amber-700 px-3 text-sm font-medium text-white disabled:opacity-50">Simpan Ketidakcocokan</button>
      </div> : null}
      {openMismatch ? <div className="mt-3 grid gap-2 border-t border-slate-200 pt-3"><p className="text-sm font-medium text-slate-900">Kontak ditolak: {openMismatch.type === "MISMATCH" ? openMismatch.rejectedEmail : ""}</p>
        <input value={replacementEmail} onChange={(event) => setReplacementEmail(event.target.value)} placeholder="Email pengganti" className="h-9 rounded-md border border-slate-300 px-2 text-sm" /><input value={confirmEmail} onChange={(event) => setConfirmEmail(event.target.value)} placeholder="Konfirmasi email pengganti" className="h-9 rounded-md border border-slate-300 px-2 text-sm" /><input value={replacementEvidence} onChange={(event) => setReplacementEvidence(event.target.value)} placeholder="https:// URL bukti resmi" className="h-9 rounded-md border border-slate-300 px-2 text-sm" /><button type="button" onClick={saveReplacement} disabled={submitting} className="h-9 rounded-md bg-slate-900 px-3 text-sm font-medium text-white">Simpan Pengganti (UNVERIFIED)</button></div> : null}
      {events.length ? <div className="mt-4 border-t border-slate-200 pt-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Riwayat</p><ul className="mt-2 space-y-1 text-xs text-slate-600">{events.map((event) => <li key={event.type === "MISMATCH" ? event.mismatchId : event.replacementId}>{event.createdAt} — {event.type === "MISMATCH" ? `Ditolak: ${event.rejectedEmail} (${event.reasonCode})` : `Pengganti: ${event.email} (UNVERIFIED saat dibuat)`}</li>)}</ul></div> : null}
    </div>
  );
}
